"""
Download Manager
Handles file downloads with progress tracking, resume support, and queue management.
"""

from __future__ import annotations

import asyncio
import errno
import logging
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Any

import aiofiles

from core.http_client import NETWORK_EXCEPTIONS, make_async_session
from core.paths import (
    PathSafetyError,
    normalize_download_path,
    safe_join,
    sanitize_filename,
    sanitize_path_segment,
)
from core import state_store

logger = logging.getLogger(__name__)

# Max items kept in completed/failed history
HISTORY_CAP = 200
# Seconds with no data before declaring a download stalled
STALL_TIMEOUT = 30
# Retry/backoff policy
BASE_RETRY_BACKOFF_SECONDS = 2
MAX_RETRY_BACKOFF_SECONDS = 60
DEFAULT_MAX_RETRIES = 3
# Disk-space safety policy
UNKNOWN_EPISODE_SIZE_BYTES = 350 * 1024 * 1024
DISK_SPACE_SAFETY_MARGIN_BYTES = 512 * 1024 * 1024


class DownloadStallError(Exception):
    """Raised when a download receives no data for STALL_TIMEOUT seconds."""


class DownloadIntegrityError(Exception):
    """Raised when response bytes or file structure fail integrity checks."""


class DownloadPausedError(Exception):
    """Raised when shutdown requests a safe pause for resume."""


class DownloadStoppedError(Exception):
    """Raised when a user stops an in-progress download."""


class DownloadHTTPError(Exception):
    """HTTP status error decoupled from the transport library."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(message or f"HTTP {status_code}")


class FileLockError(Exception):
    """Raised when a lock file indicates another writer is active."""


def _failure_from_message(message: str) -> tuple[str, str]:
    msg = (message or "").strip()
    lowered = msg.lower()

    if not msg:
        return "unknown", "No details available"

    if "no space left on device" in lowered or "insufficient disk space" in lowered:
        return "disk_full", msg
    if any(token in lowered for token in ("range not satisfiable", "size mismatch", "mp4 failed", "content-range", "content-length mismatch", "integrity")):
        return "integrity_failed", msg
    if any(token in lowered for token in ("link expired", "token", "redirect", "kwik", "forbidden", "gone")):
        return "link_expired", msg
    if any(token in lowered for token in ("timeout", "timed out", "connection", "transport", "network", "stall")):
        return "network", msg
    return "unknown", msg


def classify_failure(error: Exception | str) -> tuple[str, str]:
    if isinstance(error, str):
        return _failure_from_message(error)

    if isinstance(error, DownloadIntegrityError):
        return "integrity_failed", str(error)
    if isinstance(error, DownloadStallError):
        return "network", str(error)
    if isinstance(error, DownloadStoppedError):
        return "cancelled", str(error)
    if isinstance(error, DownloadPausedError):
        return "paused", str(error)
    if isinstance(error, FileLockError):
        return "file_conflict", str(error)
    if isinstance(error, OSError) and getattr(error, "errno", None) == errno.ENOSPC:
        return "disk_full", str(error)
    if isinstance(error, DownloadHTTPError):
        status_code = error.status_code
        if status_code in {401, 403, 404, 410}:
            return "link_expired", f"HTTP {status_code}: {error}"
        if status_code == 507:
            return "disk_full", f"HTTP {status_code}: {error}"
        if status_code >= 500:
            return "network", f"HTTP {status_code}: {error}"
        return "unknown", f"HTTP {status_code}: {error}"
    if isinstance(error, NETWORK_EXCEPTIONS):
        return "network", str(error)
    return _failure_from_message(str(error))


def _safe_int(value: Optional[str], default: int = 0) -> int:
    """Safely parse integer-like header values."""
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _parse_content_range(content_range: str) -> Optional[tuple[int, int, Optional[int]]]:
    """
    Parse Content-Range header.

    Returns (start, end, total_or_none) for valid values like:
      bytes 100-199/1000
      bytes 100-199/*
    """
    if not content_range:
        return None
    match = re.match(r"^bytes\s+(\d+)-(\d+)/(\d+|\*)$", content_range.strip())
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2))
    if end < start:
        return None
    total_raw = match.group(3)
    total = None if total_raw == "*" else int(total_raw)
    return start, end, total


def _looks_like_valid_mp4(path: str) -> bool:
    """
    Perform a lightweight MP4 box-level sanity check.

    This catches common truncation/corruption cases where container boxes are
    incomplete or missing critical atoms.
    """
    try:
        size = os.path.getsize(path)
        if size < 1024:
            return False

        saw_ftyp = False
        saw_moov = False
        saw_media = False
        offset = 0

        with open(path, "rb") as f:
            while offset + 8 <= size:
                f.seek(offset)
                header = f.read(8)
                if len(header) < 8:
                    return False

                box_size = int.from_bytes(header[:4], "big")
                box_type = header[4:8]
                header_size = 8

                if box_size == 0:
                    box_end = size
                elif box_size == 1:
                    ext_size = f.read(8)
                    if len(ext_size) < 8:
                        return False
                    box_size = int.from_bytes(ext_size, "big")
                    header_size = 16
                    if box_size < header_size:
                        return False
                    box_end = offset + box_size
                else:
                    if box_size < 8:
                        return False
                    box_end = offset + box_size

                if box_end <= offset or box_end > size:
                    return False

                if box_type == b"ftyp":
                    saw_ftyp = True
                elif box_type == b"moov":
                    saw_moov = True
                elif box_type in (b"mdat", b"moof"):
                    saw_media = True

                offset = box_end

        if offset != size:
            return False

        return saw_ftyp and saw_moov and saw_media
    except OSError:
        return False


def _is_retryable(error: Exception) -> bool:
    """Determine if a download error is worth retrying."""
    if isinstance(
        error,
        (
            DownloadStallError,
            DownloadIntegrityError,
            *NETWORK_EXCEPTIONS,
        ),
    ):
        return True
    if isinstance(error, DownloadHTTPError):
        return error.status_code >= 500
    return False


@dataclass
class DownloadTask:
    """Represents a download task."""

    id: str
    url: str
    filename: str
    anime_title: str
    episode: float
    resolution: int
    anime_session: Optional[str] = None
    episode_session: Optional[str] = None
    status: str = "pending"  # pending, downloading, completed, failed, stopped, stopping, pausing
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0  # bytes per second
    error: Optional[str] = None
    failure_reason: Optional[str] = None
    failure_detail: Optional[str] = None
    retry_count: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES
    terminal: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DownloadManager:
    """Manages concurrent downloads with progress tracking and SQLite-backed state."""

    def __init__(
        self,
        download_path: str,
        max_workers: int = 4,
        chunk_size: int = 8192,
    ):
        self.download_path = normalize_download_path(download_path)
        self.max_workers = max(1, min(8, max_workers))
        self.chunk_size = chunk_size

        self.queue: asyncio.Queue[DownloadTask] = asyncio.Queue()
        self.active_tasks: dict[str, DownloadTask] = {}
        self.completed_tasks: list[DownloadTask] = []
        self.failed_tasks: list[DownloadTask] = []

        self._workers: list[asyncio.Task] = []
        self._running = False
        self._restored = False
        self._shutdown_requested = False
        self._progress_callbacks: list[Callable[[DownloadTask], Any]] = []
        self._scaling_lock = asyncio.Lock()

        # Duplicate prevention: (anime_title, episode, resolution) -> True
        self._known_episodes: set[tuple[str, float, int]] = set()

        # Pause/resume support
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Start unpaused

        # Task id -> acquired lock file path
        self._active_lock_paths: dict[str, str] = {}

        self._metrics: dict[str, int] = {
            "downloads_started": 0,
            "downloads_completed": 0,
            "downloads_failed": 0,
            "downloads_retried": 0,
        }

        self.timeout = 60.0
        state_store.init_db()

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        self._paused = True
        self._pause_event.clear()
        logger.info("Download queue paused")

    def resume(self) -> None:
        self._paused = False
        self._pause_event.set()
        logger.info("Download queue resumed")

    def set_download_path(self, path: str) -> None:
        self.download_path = normalize_download_path(path)

    def add_progress_callback(self, callback: Callable[[DownloadTask], Any]) -> None:
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[DownloadTask], Any]) -> None:
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    async def _notify_progress(self, task: DownloadTask) -> None:
        for callback in self._progress_callbacks:
            try:
                result = callback(task)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning("Progress callback error: %s", e)

    def _append_completed(self, task: DownloadTask) -> None:
        self.completed_tasks.append(task)
        if len(self.completed_tasks) > HISTORY_CAP:
            self.completed_tasks = self.completed_tasks[-HISTORY_CAP:]

    def _append_failed(self, task: DownloadTask) -> None:
        self.failed_tasks.append(task)
        if len(self.failed_tasks) > HISTORY_CAP:
            self.failed_tasks = self.failed_tasks[-HISTORY_CAP:]

    def _episode_key(self, task: DownloadTask) -> tuple[str, float, int]:
        return (task.anime_title, task.episode, task.resolution)

    def _get_anime_folder(self, anime_title: str) -> str:
        safe_title = sanitize_path_segment(anime_title, fallback="unknown_anime")
        folder = safe_join(self.download_path, safe_title)
        os.makedirs(folder, exist_ok=True)
        return folder

    def _build_file_paths(self, task: DownloadTask) -> tuple[str, str, str]:
        folder = self._get_anime_folder(task.anime_title)
        filepath = safe_join(folder, task.filename)
        partial_path = f"{filepath}.partial"
        lock_path = f"{filepath}.lock"
        return filepath, partial_path, lock_path

    def _pending_tasks_snapshot(self) -> list[DownloadTask]:
        queue_items = getattr(self.queue, "_queue", None)
        if queue_items is None:
            return []
        return list(queue_items)

    def _task_to_record(self, task: DownloadTask) -> dict[str, Any]:
        now = datetime.now().isoformat()
        return {
            "id": task.id,
            "url": task.url,
            "filename": task.filename,
            "anime_title": task.anime_title,
            "anime_session": task.anime_session,
            "episode_session": task.episode_session,
            "episode": task.episode,
            "resolution": task.resolution,
            "status": task.status,
            "progress": float(task.progress),
            "downloaded_bytes": int(task.downloaded_bytes),
            "total_bytes": int(task.total_bytes),
            "speed": float(task.speed),
            "error": task.error,
            "failure_reason": task.failure_reason,
            "failure_detail": task.failure_detail,
            "retry_count": int(task.retry_count),
            "max_retries": int(task.max_retries),
            "terminal": 1 if task.terminal else 0,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "updated_at": now,
        }

    def _record_to_task(self, row: dict[str, Any]) -> DownloadTask:
        def parse_dt(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None

        failure_reason = row.get("failure_reason")
        failure_detail = row.get("failure_detail")
        if not failure_reason and row.get("error"):
            inferred_reason, inferred_detail = classify_failure(str(row.get("error")))
            failure_reason = inferred_reason
            failure_detail = failure_detail or inferred_detail

        return DownloadTask(
            id=row["id"],
            url=row["url"],
            filename=row["filename"],
            anime_title=row["anime_title"],
            anime_session=row.get("anime_session"),
            episode_session=row.get("episode_session"),
            episode=float(row["episode"]),
            resolution=int(row["resolution"]),
            status=row["status"],
            progress=float(row["progress"] or 0.0),
            downloaded_bytes=int(row["downloaded_bytes"] or 0),
            total_bytes=int(row["total_bytes"] or 0),
            speed=float(row["speed"] or 0.0),
            error=row["error"],
            failure_reason=failure_reason,
            failure_detail=failure_detail,
            retry_count=int(row["retry_count"] or 0),
            max_retries=int(row["max_retries"] or DEFAULT_MAX_RETRIES),
            terminal=bool(row["terminal"]),
            created_at=parse_dt(row.get("created_at")) or datetime.now(),
            started_at=parse_dt(row.get("started_at")),
            completed_at=parse_dt(row.get("completed_at")),
        )

    def _persist_task(self, task: DownloadTask) -> None:
        state_store.upsert_download_task(self._task_to_record(task))

    def _persist_tasks(self, tasks: list[DownloadTask]) -> None:
        state_store.upsert_download_tasks([self._task_to_record(t) for t in tasks])

    def _prune_history(self) -> None:
        state_store.prune_terminal_history(HISTORY_CAP)

    def _persist_runtime_state(self) -> None:
        to_persist: dict[str, DownloadTask] = {}

        for task in self._pending_tasks_snapshot():
            to_persist[task.id] = task

        for task in list(self.active_tasks.values()):
            if task.status in {"downloading", "stopping", "pausing"}:
                task.status = "pending"
                task.error = "Paused for graceful shutdown"
                task.speed = 0.0
                task.terminal = False
            to_persist[task.id] = task

        for task in self.completed_tasks:
            to_persist[task.id] = task
        for task in self.failed_tasks:
            to_persist[task.id] = task

        if to_persist:
            self._persist_tasks(list(to_persist.values()))
            self._prune_history()

    def _acquire_lock(self, task: DownloadTask, lock_path: str) -> None:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as e:
            raise FileLockError(f"Write lock already exists for {task.filename}") from e

        with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
            lock_file.write(task.id)
        self._active_lock_paths[task.id] = lock_path

    def _release_lock(self, task_id: str, lock_path: Optional[str] = None) -> None:
        target = lock_path or self._active_lock_paths.get(task_id)
        self._active_lock_paths.pop(task_id, None)
        if not target:
            return
        try:
            if os.path.exists(target):
                os.remove(target)
        except OSError:
            logger.warning("Failed to remove lock file: %s", target)

    def has_existing_task_or_file(
        self,
        anime_title: str,
        episode: float,
        resolution: int,
        filename: Optional[str] = None,
    ) -> bool:
        key = (anime_title, episode, resolution)
        if key in self._known_episodes:
            return True
        candidate_name = sanitize_filename(filename or f"EP{int(episode):02d}_{resolution}p.mp4")
        task = DownloadTask(
            id="preview",
            url="",
            filename=candidate_name,
            anime_title=anime_title,
            episode=episode,
            resolution=resolution,
        )
        filepath, _partial, lock_path = self._build_file_paths(task)
        return os.path.exists(filepath) or os.path.exists(lock_path)

    def estimate_required_bytes(self, size_bytes: list[Optional[int]]) -> int:
        known = 0
        unknown_count = 0
        for size in size_bytes:
            if size and size > 0:
                known += int(size)
            else:
                unknown_count += 1
        return known + (unknown_count * UNKNOWN_EPISODE_SIZE_BYTES)

    def disk_space_preflight(self, size_bytes: list[Optional[int]]) -> dict[str, int | bool]:
        required_bytes = self.estimate_required_bytes(size_bytes)
        usage = shutil.disk_usage(self.download_path)
        required_with_margin = required_bytes + DISK_SPACE_SAFETY_MARGIN_BYTES
        ok = usage.free >= required_with_margin
        return {
            "ok": ok,
            "required_bytes": required_bytes,
            "required_with_margin_bytes": required_with_margin,
            "free_bytes": usage.free,
        }

    async def restore_state(self) -> None:
        """Restore queue/history from SQLite and resume pending/in-progress items."""
        recovered = state_store.mark_recoverable_tasks_pending()
        if recovered:
            logger.info("Recovered %d in-progress downloads as pending", recovered)

        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.active_tasks.clear()
        self._known_episodes.clear()

        rows = state_store.load_download_tasks()
        if not rows:
            return

        loaded_tasks = [self._record_to_task(row) for row in rows]
        loaded_tasks.sort(key=lambda t: t.created_at)
        pending_tasks: list[DownloadTask] = []
        changed_tasks: list[DownloadTask] = []

        for task in loaded_tasks:
            key = self._episode_key(task)

            if task.status == "completed":
                self._known_episodes.add(key)
                self._append_completed(task)
                continue

            if task.status in {"failed", "stopped"}:
                self._append_failed(task)
                continue

            task.status = "pending"
            task.terminal = False
            task.speed = 0.0
            if task.error and task.error == "Recovered after restart":
                task.failure_reason = "recovered_after_restart"
                task.failure_detail = task.error

            try:
                filepath, _partial, _lock = self._build_file_paths(task)
            except PathSafetyError as e:
                task.status = "failed"
                task.error = f"Unsafe restored path: {e}"
                task.failure_reason = "path_error"
                task.failure_detail = str(e)
                task.terminal = True
                self._append_failed(task)
                changed_tasks.append(task)
                continue

            if os.path.exists(filepath):
                if not filepath.lower().endswith(".mp4") or _looks_like_valid_mp4(filepath):
                    task.status = "completed"
                    task.progress = 100.0
                    task.error = None
                    task.failure_reason = None
                    task.failure_detail = None
                    task.terminal = False
                    task.completed_at = task.completed_at or datetime.now()
                    self._known_episodes.add(key)
                    self._append_completed(task)
                    changed_tasks.append(task)
                    continue

            self._known_episodes.add(key)
            pending_tasks.append(task)

        pending_tasks.sort(key=lambda t: t.created_at)
        for task in pending_tasks:
            await self.queue.put(task)

        if changed_tasks:
            self._persist_tasks(changed_tasks)
            self._prune_history()

    async def cleanup_stale_partials(self) -> int:
        """
        Remove stale .partial and .lock files that are not associated with
        persisted pending/in-progress tasks.
        """
        rows = state_store.load_download_tasks()
        keep_partials: set[str] = set()
        keep_locks: set[str] = set()

        for row in rows:
            status = row.get("status")
            if status not in {"pending", "downloading", "stopping", "pausing"}:
                continue
            task = self._record_to_task(row)
            try:
                _filepath, partial, lock = self._build_file_paths(task)
            except PathSafetyError:
                continue
            keep_partials.add(partial)
            keep_locks.add(lock)

        removed = 0
        for root, _dirs, files in os.walk(self.download_path):
            for name in files:
                path = os.path.join(root, name)
                if name.endswith(".partial") and path not in keep_partials:
                    try:
                        os.remove(path)
                        removed += 1
                    except OSError:
                        pass
                if name.endswith(".lock") and path not in keep_locks:
                    try:
                        os.remove(path)
                        removed += 1
                    except OSError:
                        pass
        if removed:
            logger.info("Cleaned up %d stale partial/lock files", removed)
        return removed

    async def cleanup_orphan_queue_entries(self) -> int:
        """
        Remove persisted in-flight queue entries that are no longer present in
        the in-memory queue or active task map.
        """
        runtime_ids = {task.id for task in self._pending_tasks_snapshot()}
        runtime_ids.update(self.active_tasks.keys())

        orphan_ids: list[str] = []
        for row in state_store.load_download_tasks():
            status = row.get("status")
            task_id = row.get("id")
            if not task_id or status not in {"pending", "downloading", "stopping", "pausing"}:
                continue
            if task_id not in runtime_ids:
                orphan_ids.append(task_id)

        if orphan_ids:
            state_store.delete_download_tasks(orphan_ids)
            logger.info("Removed %d orphan queue entries", len(orphan_ids))
        return len(orphan_ids)

    async def reload_state_from_store(self) -> None:
        """Clear in-memory queue/history and rebuild from SQLite state."""
        queue_items = getattr(self.queue, "_queue", None)
        if queue_items is not None:
            queue_items.clear()

        self.completed_tasks.clear()
        self.failed_tasks.clear()
        self.active_tasks.clear()
        self._known_episodes.clear()

        await self.restore_state()

    async def add_task(
        self,
        url: str,
        anime_title: str,
        episode: float,
        resolution: int,
        filename: Optional[str] = None,
        anime_session: Optional[str] = None,
        episode_session: Optional[str] = None,
    ) -> Optional[DownloadTask]:
        candidate_name = sanitize_filename(filename or f"EP{int(episode):02d}_{resolution}p.mp4")

        key = (anime_title, episode, resolution)

        preview = DownloadTask(
            id="preview",
            url=url,
            filename=candidate_name,
            anime_title=anime_title,
            anime_session=anime_session,
            episode_session=episode_session,
            episode=episode,
            resolution=resolution,
        )
        _filepath, _partial_path, lock_path = self._build_file_paths(preview)
        if os.path.exists(lock_path):
            logger.debug("File lock already exists, skipping conflicting write: %s", lock_path)
            return None

        self._known_episodes.add(key)
        task = DownloadTask(
            id=str(uuid.uuid4()),
            url=url,
            filename=candidate_name,
            anime_title=anime_title,
            anime_session=anime_session,
            episode_session=episode_session,
            episode=episode,
            resolution=resolution,
        )

        await self.queue.put(task)
        self._persist_task(task)
        await self._notify_progress(task)
        return task

    async def _download_file(self, task: DownloadTask) -> None:
        """Download a single file with progress tracking, resume, and integrity checks."""
        task.status = "downloading"
        first_start = task.started_at is None
        task.started_at = task.started_at or datetime.now()
        task.error = None
        task.failure_reason = None
        task.failure_detail = None
        task.terminal = False
        if first_start:
            self._metrics["downloads_started"] += 1
        self.active_tasks[task.id] = task
        self._persist_task(task)
        await self._notify_progress(task)

        filepath = None
        partial_path = None
        lock_path = None

        try:
            filepath, partial_path, lock_path = self._build_file_paths(task)
            self._acquire_lock(task, lock_path)

            headers = {
                "Referer": "https://kwik.cx/",
                "Accept-Encoding": "identity",
            }

            existing_bytes = 0
            if os.path.exists(partial_path):
                existing_bytes = os.path.getsize(partial_path)
                if existing_bytes > 0:
                    headers["Range"] = f"bytes={existing_bytes}-"
                    task.downloaded_bytes = existing_bytes

            async with make_async_session(timeout=self.timeout) as session:
                async with session.stream("GET", task.url, headers=headers, allow_redirects=True) as response:
                    status = response.status_code
                    response_content_length = _safe_int(response.headers.get("content-length"), 0)
                    bytes_received_this_response = 0
                    expected_total_size = 0

                    if status == 416:
                        if os.path.exists(partial_path):
                            os.remove(partial_path)
                        existing_bytes = 0
                        task.downloaded_bytes = 0
                        raise DownloadIntegrityError("Range not satisfiable, restarting from zero")

                    if status >= 400:
                        raise DownloadHTTPError(status)

                    if status == 206 and existing_bytes > 0:
                        parsed_range = _parse_content_range(response.headers.get("content-range", ""))
                        if not parsed_range:
                            raise DownloadIntegrityError("Missing/invalid Content-Range for resumed download")

                        range_start, range_end, range_total = parsed_range
                        if range_start != existing_bytes:
                            raise DownloadIntegrityError(
                                f"Resume offset mismatch (expected {existing_bytes}, got {range_start})"
                            )

                        range_length = (range_end - range_start) + 1
                        if response_content_length > 0 and response_content_length != range_length:
                            raise DownloadIntegrityError("Content-Length mismatch with Content-Range span")

                        file_mode = "ab"
                        if range_total is not None:
                            task.total_bytes = range_total
                            expected_total_size = range_total
                        elif response_content_length > 0:
                            task.total_bytes = existing_bytes + response_content_length
                            expected_total_size = task.total_bytes
                        else:
                            task.total_bytes = 0
                            expected_total_size = 0
                    else:
                        if status == 206 and existing_bytes == 0:
                            raise DownloadIntegrityError("Received partial response for fresh download")

                        file_mode = "wb"
                        task.downloaded_bytes = 0
                        existing_bytes = 0
                        task.total_bytes = response_content_length
                        expected_total_size = response_content_length

                    last_update = datetime.now()
                    last_bytes = task.downloaded_bytes

                    async with aiofiles.open(partial_path, file_mode) as f:
                        aiterator = response.aiter_content(chunk_size=self.chunk_size)
                        while True:
                            try:
                                chunk = await asyncio.wait_for(
                                    aiterator.__anext__(),
                                    timeout=STALL_TIMEOUT,
                                )
                            except StopAsyncIteration:
                                break
                            except asyncio.TimeoutError:
                                raise DownloadStallError(f"No data for {STALL_TIMEOUT}s")

                            if self._shutdown_requested:
                                raise DownloadPausedError("Paused for graceful shutdown")
                            if task.status == "stopping":
                                raise DownloadStoppedError("Download stopped by user")
                            if not chunk:
                                continue
                            await f.write(chunk)
                            bytes_received_this_response += len(chunk)
                            task.downloaded_bytes += len(chunk)

                            if task.total_bytes > 0:
                                task.progress = (task.downloaded_bytes / task.total_bytes) * 100

                            now = datetime.now()
                            elapsed = (now - last_update).total_seconds()
                            if elapsed >= 1.0:
                                bytes_diff = task.downloaded_bytes - last_bytes
                                task.speed = bytes_diff / elapsed
                                last_update = now
                                last_bytes = task.downloaded_bytes
                                self._persist_task(task)
                                await self._notify_progress(task)

                    if response_content_length > 0 and bytes_received_this_response != response_content_length:
                        raise DownloadIntegrityError("Response body ended before expected Content-Length")

            final_size = os.path.getsize(partial_path)
            if expected_total_size > 0 and final_size != expected_total_size:
                raise DownloadIntegrityError(
                    f"Downloaded file size mismatch (expected {expected_total_size}, got {final_size})"
                )

            if filepath.lower().endswith(".mp4") and not _looks_like_valid_mp4(partial_path):
                raise DownloadIntegrityError("Downloaded MP4 failed container validation")

            os.replace(partial_path, filepath)

            task.status = "completed"
            task.progress = 100.0
            task.speed = 0.0
            task.error = None
            task.failure_reason = None
            task.failure_detail = None
            task.terminal = False
            task.completed_at = datetime.now()
            self._metrics["downloads_completed"] += 1
            self._append_completed(task)
            self._persist_task(task)
            self._prune_history()

        except DownloadPausedError as e:
            task.status = "pending"
            task.error = str(e)
            task.failure_reason, task.failure_detail = classify_failure(e)
            task.speed = 0.0
            task.terminal = False
            self._persist_task(task)

        except DownloadStoppedError as e:
            task.status = "stopped"
            task.error = str(e)
            task.failure_reason, task.failure_detail = classify_failure(e)
            task.speed = 0.0
            task.terminal = True
            self._append_failed(task)
            self._persist_task(task)
            self._prune_history()

        except asyncio.CancelledError:
            if self._shutdown_requested:
                task.status = "pending"
                task.error = "Paused for graceful shutdown"
                task.failure_reason = "paused"
                task.failure_detail = task.error
                task.speed = 0.0
                task.terminal = False
                self._persist_task(task)
            else:
                task.status = "stopped"
                task.error = "Download stopped"
                task.failure_reason = "cancelled"
                task.failure_detail = task.error
                task.speed = 0.0
                task.terminal = True
                self._append_failed(task)
                self._persist_task(task)
                self._prune_history()
            raise

        except Exception as e:
            if _is_retryable(e) and task.retry_count < task.max_retries:
                task.retry_count += 1
                self._metrics["downloads_retried"] += 1
                backoff = min(
                    MAX_RETRY_BACKOFF_SECONDS,
                    BASE_RETRY_BACKOFF_SECONDS * (2 ** (task.retry_count - 1)),
                )
                failure_reason, failure_detail = classify_failure(e)
                task.status = "pending"
                task.error = f"Retry {task.retry_count}/{task.max_retries} in {backoff}s: {e}"
                task.failure_reason = failure_reason
                task.failure_detail = failure_detail
                task.speed = 0.0
                task.terminal = False
                logger.info(
                    "Retrying %s (attempt %d/%d in %ss): %s",
                    task.filename, task.retry_count, task.max_retries, backoff, e,
                )
                self._persist_task(task)
                await self._notify_progress(task)
                await asyncio.sleep(backoff)
                if self._running and not self._shutdown_requested:
                    await self.queue.put(task)
                return

            failure_reason, failure_detail = classify_failure(e)
            task.status = "failed"
            task.error = f"Terminal failure after {task.retry_count}/{task.max_retries} retries: {e}"
            task.failure_reason = failure_reason
            task.failure_detail = failure_detail
            task.speed = 0.0
            task.terminal = True
            self._metrics["downloads_failed"] += 1
            self._append_failed(task)
            self._persist_task(task)
            self._prune_history()

            if partial_path and isinstance(e, DownloadIntegrityError) and os.path.exists(partial_path):
                try:
                    os.remove(partial_path)
                except OSError:
                    pass

        finally:
            self._release_lock(task.id, lock_path)
            key = self._episode_key(task)
            if task.status in ("failed", "stopped"):
                self._known_episodes.discard(key)
            self.active_tasks.pop(task.id, None)
            await self._notify_progress(task)

    async def _worker(self, worker_id: int) -> None:
        try:
            while self._running:
                if worker_id >= self.max_workers:
                    break

                await self._pause_event.wait()
                try:
                    task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                try:
                    await self._download_file(task)
                finally:
                    self.queue.task_done()
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error("Worker %d error: %s", worker_id, e)

    async def adjust_workers(self, new_count: int) -> None:
        async with self._scaling_lock:
            new_count = max(1, min(8, new_count))
            old_count = len(self._workers)
            self.max_workers = new_count
            if not self._running:
                return
            if new_count > old_count:
                for i in range(old_count, new_count):
                    self._workers.append(asyncio.create_task(self._worker(i)))
            self._workers = [w for w in self._workers if not w.done()]

    async def start(self) -> None:
        if self._running:
            return
        if not self._restored:
            await self.restore_state()
            self._restored = True
        self._shutdown_requested = False
        self._running = True
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(self.max_workers)]

    async def stop(self) -> None:
        self._shutdown_requested = True
        self._running = False
        self._pause_event.set()

        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []

        self._persist_runtime_state()
        self._shutdown_requested = False

    def get_status(self) -> dict:
        pending = self._pending_tasks_snapshot()
        return {
            "running": self._running,
            "max_workers": self.max_workers,
            "pending_count": len(pending),
            "active_count": len(self.active_tasks),
            "completed_count": len(self.completed_tasks),
            "failed_count": len(self.failed_tasks),
            "active": [self._task_to_dict(t) for t in self.active_tasks.values()],
            "pending": [self._task_to_dict(t) for t in pending],
            "completed": [self._task_to_dict(t) for t in self.completed_tasks[-10:]],
            "failed": [self._task_to_dict(t) for t in self.failed_tasks[-10:]],
        }

    def _task_to_dict(self, task: DownloadTask) -> dict:
        return {
            "id": task.id,
            "filename": task.filename,
            "anime_title": task.anime_title,
            "anime_session": task.anime_session,
            "episode_session": task.episode_session,
            "episode": task.episode,
            "resolution": task.resolution,
            "status": task.status,
            "progress": round(task.progress, 1),
            "downloaded_bytes": task.downloaded_bytes,
            "total_bytes": task.total_bytes,
            "speed": round(task.speed, 0),
            "error": task.error,
            "failure_reason": task.failure_reason,
            "failure_detail": task.failure_detail,
            "retry_count": task.retry_count,
            "terminal": task.terminal,
        }

    def get_metrics(self) -> dict[str, int]:
        return dict(self._metrics)

    def find_task(self, task_id: str) -> Optional[DownloadTask]:
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]

        for task in self._pending_tasks_snapshot():
            if task.id == task_id:
                return task

        for task in self.completed_tasks:
            if task.id == task_id:
                return task

        for task in self.failed_tasks:
            if task.id == task_id:
                return task

        return None

    async def retry_task(self, task_id: str) -> Optional[DownloadTask]:
        task = next((item for item in self.failed_tasks if item.id == task_id), None)
        if not task:
            return None

        new_task = DownloadTask(
            id=str(uuid.uuid4()),
            url=task.url,
            filename=task.filename,
            anime_title=task.anime_title,
            anime_session=task.anime_session,
            episode_session=task.episode_session,
            episode=task.episode,
            resolution=task.resolution,
        )
        self._known_episodes.add(self._episode_key(new_task))
        await self.queue.put(new_task)
        self.failed_tasks.remove(task)
        state_store.delete_download_task(task.id)
        self._persist_task(new_task)
        self._metrics["downloads_retried"] += 1
        return new_task

    def revalidate_task_file(self, task_id: str) -> dict[str, Any]:
        task = self.find_task(task_id)
        if not task:
            return {"found": False, "valid": False, "message": "Task not found"}

        try:
            filepath, _partial, _lock = self._build_file_paths(task)
        except PathSafetyError as e:
            detail = f"Path validation failed: {e}"
            task.status = "failed"
            task.error = detail
            task.failure_reason = "path_error"
            task.failure_detail = str(e)
            task.terminal = True
            self.completed_tasks = [item for item in self.completed_tasks if item.id != task.id]
            self.failed_tasks = [item for item in self.failed_tasks if item.id != task.id]
            self._append_failed(task)
            self._known_episodes.discard(self._episode_key(task))
            self._persist_task(task)
            self._prune_history()
            return {"found": True, "valid": False, "message": detail}

        if not os.path.exists(filepath):
            detail = "File is missing on disk"
            task.status = "failed"
            task.error = detail
            task.failure_reason = "integrity_failed"
            task.failure_detail = detail
            task.terminal = True
            self.completed_tasks = [item for item in self.completed_tasks if item.id != task.id]
            self.failed_tasks = [item for item in self.failed_tasks if item.id != task.id]
            self._append_failed(task)
            self._known_episodes.discard(self._episode_key(task))
            self._persist_task(task)
            self._prune_history()
            return {"found": True, "valid": False, "message": detail}

        if filepath.lower().endswith(".mp4") and not _looks_like_valid_mp4(filepath):
            detail = "MP4 integrity check failed"
            task.status = "failed"
            task.error = detail
            task.failure_reason = "integrity_failed"
            task.failure_detail = detail
            task.terminal = True
            self.completed_tasks = [item for item in self.completed_tasks if item.id != task.id]
            self.failed_tasks = [item for item in self.failed_tasks if item.id != task.id]
            self._append_failed(task)
            self._known_episodes.discard(self._episode_key(task))
            self._persist_task(task)
            self._prune_history()
            return {"found": True, "valid": False, "message": detail}

        task.failure_reason = None
        task.failure_detail = None
        if task.status != "completed":
            task.status = "completed"
            task.progress = 100.0
            task.error = None
            task.terminal = False
            task.completed_at = datetime.now()
            self.failed_tasks = [item for item in self.failed_tasks if item.id != task.id]
            if not any(item.id == task.id for item in self.completed_tasks):
                self._append_completed(task)
            self._persist_task(task)
            self._prune_history()

        return {"found": True, "valid": True, "message": "File integrity validation passed"}

    async def cancel_task(self, task_id: str) -> bool:
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.status = "stopping"
            task.error = "Stopping..."
            task.failure_reason = "cancelled"
            task.failure_detail = task.error
            self._persist_task(task)
            return True

        queue_items = getattr(self.queue, "_queue", None)
        if queue_items is None:
            return False

        found: Optional[DownloadTask] = None
        for item in list(queue_items):
            if item.id == task_id:
                queue_items.remove(item)
                found = item
                break

        if not found:
            return False

        found.status = "stopped"
        found.error = "Cancelled before starting"
        found.failure_reason = "cancelled"
        found.failure_detail = found.error
        found.terminal = True
        self._append_failed(found)
        self._known_episodes.discard(self._episode_key(found))
        self._persist_task(found)
        self._prune_history()

        try:
            self.queue.task_done()
        except ValueError:
            pass
        return True

    async def cancel_all_tasks(self) -> int:
        count = 0
        for task_id in list(self.active_tasks.keys()):
            if await self.cancel_task(task_id):
                count += 1

        queue_items = getattr(self.queue, "_queue", None)
        if queue_items is not None:
            pending_items = list(queue_items)
            queue_items.clear()
            for item in pending_items:
                item.status = "stopped"
                item.error = "Cancelled by user"
                item.failure_reason = "cancelled"
                item.failure_detail = item.error
                item.terminal = True
                self._append_failed(item)
                self._known_episodes.discard(self._episode_key(item))
                self._persist_task(item)
                count += 1
                try:
                    self.queue.task_done()
                except ValueError:
                    pass

        self._prune_history()
        return count

    async def retry_failed(self) -> int:
        retry_count = 0
        for task in self.failed_tasks[:]:
            new_task = DownloadTask(
                id=str(uuid.uuid4()),
                url=task.url,
                filename=task.filename,
                anime_title=task.anime_title,
                anime_session=task.anime_session,
                episode_session=task.episode_session,
                episode=task.episode,
                resolution=task.resolution,
            )
            self._known_episodes.add(self._episode_key(new_task))
            await self.queue.put(new_task)
            self.failed_tasks.remove(task)
            state_store.delete_download_task(task.id)
            self._persist_task(new_task)
            self._metrics["downloads_retried"] += 1
            retry_count += 1
        return retry_count

    def clear_completed(self) -> int:
        count = len(self.completed_tasks)
        for task in self.completed_tasks:
            self._known_episodes.discard(self._episode_key(task))
            state_store.delete_download_task(task.id)
        self.completed_tasks.clear()
        return count
