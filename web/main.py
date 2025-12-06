"""
AnimePahe Web Downloader - FastAPI Application
"""

import os
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as api_router, init_clients
from core.animepahe import AnimePaheClient
from core.downloader import DownloadManager


# Get default download path (user's Downloads folder)
def get_default_download_path() -> str:
    """Get the default download path (user's Downloads folder)"""
    # Try to get the Downloads folder
    if os.name == 'nt':  # Windows
        import winreg
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            ) as key:
                downloads_path = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
                return downloads_path
        except Exception:
            pass
    
    # Fallback to ~/Downloads
    home = Path.home()
    downloads = home / "Downloads"
    return str(downloads)


# Global instances
animepahe_client = AnimePaheClient()
download_manager: DownloadManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global download_manager
    
    # Startup
    default_path = get_default_download_path()
    os.makedirs(default_path, exist_ok=True)
    
    download_manager = DownloadManager(
        download_path=default_path,
        max_workers=4
    )
    
    # Initialize API clients
    init_clients(animepahe_client, download_manager)
    
    # Start download workers
    await download_manager.start()
    
    print(f"🚀 AnimePahe Web Downloader started!")
    print(f"📁 Default download path: {default_path}")
    print(f"🌐 Open http://localhost:8000 in your browser")
    
    yield
    
    # Shutdown
    await download_manager.stop()
    print("👋 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="AnimePahe Web Downloader",
    description="A modern web interface for downloading anime from AnimePahe",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Serve static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page"""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "AnimePahe Web Downloader API", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "download_path": download_manager.download_path if download_manager else None,
        "workers_active": download_manager._running if download_manager else False
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)]
    )
