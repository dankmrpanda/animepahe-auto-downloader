"""
AnimePahe Web Downloader - FastAPI Application
"""

import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core.logger import setup_logging
from core.config import load_config, Config
from api.routes import router as api_router, init_clients
from core.animepahe import AnimePaheClient
from core.downloader import DownloadManager
from core.diagnostics import run_environment_checks, build_health_payload

setup_logging()
logger = logging.getLogger(__name__)

# Global instances
animepahe_client = AnimePaheClient()
download_manager: DownloadManager = None
app_config: Config = None
startup_checks: dict = {}
app_started_at: str = datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global download_manager, app_config, startup_checks, app_started_at

    # Load persisted config
    app_config = load_config()
    os.makedirs(app_config.download_path, exist_ok=True)

    startup_checks = await run_environment_checks(app_config.download_path)
    app_started_at = datetime.now(timezone.utc).isoformat()
    app.state.startup_checks = startup_checks
    app.state.started_at = app_started_at

    path_exists_ok = startup_checks["checks"]["path_exists"]["ok"]
    path_writable_ok = startup_checks["checks"]["path_writable"]["ok"]
    if not path_exists_ok or not path_writable_ok:
        detail = startup_checks["checks"]["path_writable"]["detail"]
        logger.error("Startup self-check failed: %s", detail)
        raise RuntimeError(f"Startup self-check failed: {detail}")

    if not startup_checks["checks"]["internet_reachability"]["ok"]:
        logger.warning(
            "Startup internet reachability check failed: %s",
            startup_checks["checks"]["internet_reachability"]["detail"],
        )

    download_manager = DownloadManager(
        download_path=app_config.download_path,
        max_workers=app_config.max_workers,
    )

    # Initialize API clients
    init_clients(animepahe_client, download_manager, app_config)

    # Clean up stale partial downloads
    await download_manager.cleanup_stale_partials()

    # Start download workers
    await download_manager.start()

    logger.info("AnimePahe Web Downloader started!")
    logger.info("Download path: %s", app_config.download_path)
    logger.info("Open http://localhost:8000 in your browser")

    yield

    # Shutdown
    await download_manager.stop()
    await animepahe_client.close()
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="AnimePahe Web Downloader",
    description="A modern web interface for downloading anime from AnimePahe",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - restricted to localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return build_health_payload(
        download_manager=download_manager,
        startup_checks=startup_checks,
        started_at=app_started_at,
    )


# Serve static files (Production build)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {
            "message": "AnimePahe Web Downloader API",
            "status": "running",
            "frontend": "Run 'npm run dev' in frontend directory for development, or 'npm run build' for production.",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
