"""
Download Manager
Handles file downloads with progress tracking and queue management
"""

import os
import re
import asyncio
import httpx
import aiofiles
from urllib.parse import unquote
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime
import uuid


@dataclass
class DownloadTask:
    """Represents a download task"""
    id: str
    url: str
    filename: str
    anime_title: str
    episode: float
    resolution: int
    status: str = "pending"  # pending, downloading, completed, failed, cancelled
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0  # bytes per second
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    

class DownloadManager:
    """Manages concurrent downloads with progress tracking"""
    
    def __init__(
        self, 
        download_path: str,
        max_workers: int = 4,
        chunk_size: int = 8192
    ):
        self.download_path = download_path
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        
        self.queue: asyncio.Queue[DownloadTask] = asyncio.Queue()
        self.active_tasks: dict[str, DownloadTask] = {}
        self.completed_tasks: list[DownloadTask] = []
        self.failed_tasks: list[DownloadTask] = []
        
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._progress_callbacks: list[Callable[[DownloadTask], Any]] = []
        
        self.timeout = httpx.Timeout(60.0, connect=30.0)
    
    def set_download_path(self, path: str) -> None:
        """Update the download path"""
        self.download_path = path
    
    def add_progress_callback(self, callback: Callable[[DownloadTask], Any]) -> None:
        """Add a callback to be called on progress updates"""
        self._progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[DownloadTask], Any]) -> None:
        """Remove a progress callback"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
    
    async def _notify_progress(self, task: DownloadTask) -> None:
        """Notify all callbacks about progress update"""
        for callback in self._progress_callbacks:
            try:
                result = callback(task)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                print(f"Progress callback error: {e}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename"""
        return "".join(c for c in filename if c not in r'<>:"/\|?*')
    
    def _get_anime_folder(self, anime_title: str) -> str:
        """Get or create anime-specific download folder"""
        safe_title = self._sanitize_filename(anime_title)
        folder = os.path.join(self.download_path, safe_title)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    async def add_task(
        self, 
        url: str, 
        anime_title: str,
        episode: float,
        resolution: int,
        filename: Optional[str] = None
    ) -> DownloadTask:
        """
        Add a download task to the queue.
        
        Args:
            url: Direct download URL
            anime_title: Title of the anime (for folder organization)
            episode: Episode number
            resolution: Video resolution
            filename: Optional custom filename
            
        Returns:
            The created DownloadTask
        """
        if not filename:
            filename = f"EP{int(episode):02d}_{resolution}p.mp4"
        
        task = DownloadTask(
            id=str(uuid.uuid4()),
            url=url,
            filename=filename,
            anime_title=anime_title,
            episode=episode,
            resolution=resolution,
        )
        
        await self.queue.put(task)
        await self._notify_progress(task)
        
        return task
    
    async def _download_file(self, task: DownloadTask) -> None:
        """Download a single file with progress tracking"""
        task.status = "downloading"
        task.started_at = datetime.now()
        self.active_tasks[task.id] = task
        await self._notify_progress(task)
        
        filepath = None
        try:
            folder = self._get_anime_folder(task.anime_title)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Add headers for download (Referer is often required)
                headers = {
                    "Referer": "https://kwik.cx/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                async with client.stream("GET", task.url, headers=headers, follow_redirects=True) as response:
                    response.raise_for_status()
                    
                    # Try to get filename from Content-Disposition
                    content_disp = response.headers.get("content-disposition", "")
                    if content_disp:
                        match = re.search(r'filename="([^"]+)"', content_disp)
                        if match:
                            task.filename = self._sanitize_filename(unquote(match.group(1)))
                    
                    filepath = os.path.join(folder, task.filename)
                    task.total_bytes = int(response.headers.get("content-length", 0))
                    
                    last_update = datetime.now()
                    last_bytes = 0
                    
                    async with aiofiles.open(filepath, "wb") as f:
                        async for chunk in response.aiter_bytes(self.chunk_size):
                            # Check for cancellation
                            if task.status == "stopping":
                                task.status = "stopped"
                                task.error = "Download stopped by user"
                                self.failed_tasks.append(task)
                                # Delete partial file
                                try:
                                    await f.close()
                                    if filepath and os.path.exists(filepath):
                                        os.remove(filepath)
                                except:
                                    pass
                                return
                            
                            await f.write(chunk)
                            task.downloaded_bytes += len(chunk)
                            
                            # Calculate progress and speed
                            if task.total_bytes > 0:
                                task.progress = (task.downloaded_bytes / task.total_bytes) * 100
                            
                            # Update speed every second
                            now = datetime.now()
                            elapsed = (now - last_update).total_seconds()
                            if elapsed >= 1.0:
                                bytes_diff = task.downloaded_bytes - last_bytes
                                task.speed = bytes_diff / elapsed
                                last_update = now
                                last_bytes = task.downloaded_bytes
                                await self._notify_progress(task)
            
            task.status = "completed"
            task.progress = 100.0
            task.completed_at = datetime.now()
            self.completed_tasks.append(task)
            
        except asyncio.CancelledError:
            task.status = "stopped"
            task.error = "Download stopped"
            self.failed_tasks.append(task)
            # Clean up partial file
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            raise
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self.failed_tasks.append(task)
            
        finally:
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            await self._notify_progress(task)
    
    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes download tasks"""
        while self._running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                await self._download_file(task)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
    
    async def start(self) -> None:
        """Start the download workers"""
        if self._running:
            return
        
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_workers)
        ]
    
    async def stop(self) -> None:
        """Stop all workers and cancel pending downloads"""
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers = []
    
    def get_status(self) -> dict:
        """Get current download manager status"""
        pending_list = []
        try:
            # Get items from queue without blocking
            items = []
            while not self.queue.empty():
                try:
                    item = self.queue.get_nowait()
                    items.append(item)
                except asyncio.QueueEmpty:
                    break
            
            # Put items back
            for item in items:
                self.queue.put_nowait(item)
            
            pending_list = [self._task_to_dict(t) for t in items]
        except Exception:
            pass
        
        return {
            "running": self._running,
            "max_workers": self.max_workers,
            "pending_count": self.queue.qsize(),
            "active_count": len(self.active_tasks),
            "completed_count": len(self.completed_tasks),
            "failed_count": len(self.failed_tasks),
            "active": [self._task_to_dict(t) for t in self.active_tasks.values()],
            "pending": pending_list,
            "completed": [self._task_to_dict(t) for t in self.completed_tasks[-10:]],
            "failed": [self._task_to_dict(t) for t in self.failed_tasks[-10:]],
        }
    
    def _task_to_dict(self, task: DownloadTask) -> dict:
        """Convert a task to a dictionary for JSON serialization"""
        return {
            "id": task.id,
            "filename": task.filename,
            "anime_title": task.anime_title,
            "episode": task.episode,
            "resolution": task.resolution,
            "status": task.status,
            "progress": round(task.progress, 1),
            "downloaded_bytes": task.downloaded_bytes,
            "total_bytes": task.total_bytes,
            "speed": round(task.speed, 0),
            "error": task.error,
        }
    
    async def cancel_task(self, task_id: str) -> bool:
        """Stop a pending or active download"""
        # Check if it's in active tasks
        if task_id in self.active_tasks:
            # Mark for stopping - the download loop will check this
            self.active_tasks[task_id].status = "stopping"
            return True
        
        # For pending tasks, mark them so they get skipped
        # We need to go through the queue
        items = []
        found = False
        while not self.queue.empty():
            try:
                item = self.queue.get_nowait()
                if item.id == task_id:
                    item.status = "stopped"
                    item.error = "Cancelled before starting"
                    self.failed_tasks.append(item)
                    found = True
                else:
                    items.append(item)
            except asyncio.QueueEmpty:
                break
        
        # Put remaining items back
        for item in items:
            self.queue.put_nowait(item)
        
        return found
    
    async def retry_failed(self) -> int:
        """Retry all failed downloads"""
        retry_count = 0
        
        for task in self.failed_tasks[:]:
            new_task = DownloadTask(
                id=str(uuid.uuid4()),
                url=task.url,
                filename=task.filename,
                anime_title=task.anime_title,
                episode=task.episode,
                resolution=task.resolution,
            )
            await self.queue.put(new_task)
            self.failed_tasks.remove(task)
            retry_count += 1
        
        return retry_count
    
    def clear_completed(self) -> int:
        """Clear completed tasks from history"""
        count = len(self.completed_tasks)
        self.completed_tasks.clear()
        return count
