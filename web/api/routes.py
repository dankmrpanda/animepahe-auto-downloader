"""
API Routes for AnimePahe Web Downloader
"""

import os
import sys
import uuid
import logging
import asyncio
from datetime import datetime, timezone
import subprocess
from fastapi import APIRouter, Body, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from typing import Optional

from api.models import (
    SearchResponse, AnimeSearchResult, AnimeDetails, Episode,
    EpisodesResponse, EpisodeLinksResponse, DownloadOption,
    DownloadRequest, BatchDownloadRequest, DownloadQueueStatus,
    AppSettings, UpdateSettingsRequest, DownloadProgress
)
from core.animepahe import AnimePaheClient, AnimePaheError
from core.downloader import DownloadManager, DownloadTask, classify_failure
from core.config import Config, save_config
from core.paths import PathSafetyError, normalize_download_path
from core import state_store
from core.diagnostics import build_health_payload, collect_recent_errors, run_environment_checks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

# Initialize clients (will be set by main.py)
animepahe_client: Optional[AnimePaheClient] = None
download_manager: Optional[DownloadManager] = None
app_config: Optional[Config] = None

# WebSocket connections for progress updates
connected_websockets: set[WebSocket] = set()


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def _disk_space_error(preflight: dict) -> str:
    return (
        "Insufficient disk space: "
        f"required {_format_bytes(preflight['required_with_margin_bytes'])} "
        f"(including safety margin), available {_format_bytes(preflight['free_bytes'])}"
    )


def init_clients(client: AnimePaheClient, manager: DownloadManager, config: Config):
    """Initialize the API clients"""
    global animepahe_client, download_manager, app_config
    animepahe_client = client
    download_manager = manager
    app_config = config

    # Add progress callback
    async def progress_callback(task: DownloadTask):
        await broadcast_progress(task)
        if task.status in {"completed", "failed", "stopped"}:
            await broadcast_status()

    download_manager.add_progress_callback(progress_callback)


# ============= WebSocket Broadcast Helpers =============

async def _broadcast(message: dict):
    """Send a message to all connected WebSocket clients."""
    if not connected_websockets:
        return
    disconnected = set()
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.add(ws)
    connected_websockets.difference_update(disconnected)


async def broadcast_progress(task: DownloadTask):
    if not download_manager:
        return
    await _broadcast({"type": "progress", "task": download_manager._task_to_dict(task)})


async def broadcast_status():
    if not download_manager:
        return
    status = download_manager.get_status()
    status["paused"] = download_manager.is_paused
    await _broadcast({"type": "status", "queue": status})


async def broadcast_link_progress(processed: int, total: int):
    await _broadcast({"type": "link_progress", "processed": processed, "total": total})


async def broadcast_settings():
    if not download_manager:
        return
    await _broadcast({
        "type": "settings",
        "settings": {
            "download_path": download_manager.download_path,
            "max_workers": download_manager.max_workers,
        },
    })


async def broadcast_link_error(error_msg: str, anime_title: str):
    reason, detail = classify_failure(error_msg)
    await _broadcast({
        "type": "link_error",
        "error": error_msg,
        "reason": reason,
        "detail": detail,
        "anime_title": anime_title,
    })


def _select_download_option(options: list[DownloadOption], target_resolution: int) -> DownloadOption:
    if not options:
        raise ValueError("No download options available")
    if target_resolution == 0:
        return max(options, key=lambda x: x.resolution)
    if target_resolution == -1:
        return min(options, key=lambda x: x.resolution)
    for opt in options:
        if opt.resolution == target_resolution:
            return opt
    return max(options, key=lambda x: x.resolution)


def _normalize_import_task(raw: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    status = str(raw.get("status") or "pending").strip().lower()
    if status not in {"pending", "downloading", "completed", "failed", "stopped", "stopping", "pausing"}:
        status = "pending"

    retry_count = int(raw.get("retry_count") or 0)
    max_retries = int(raw.get("max_retries") or 3)
    terminal = bool(raw.get("terminal"))

    return {
        "id": str(raw.get("id") or str(uuid.uuid4())),
        "url": str(raw.get("url") or ""),
        "filename": str(raw.get("filename") or "unknown.mp4"),
        "anime_title": str(raw.get("anime_title") or "Unknown"),
        "anime_session": raw.get("anime_session"),
        "episode_session": raw.get("episode_session"),
        "episode": float(raw.get("episode") or 0.0),
        "resolution": int(raw.get("resolution") or 0),
        "status": status,
        "progress": float(raw.get("progress") or 0.0),
        "downloaded_bytes": int(raw.get("downloaded_bytes") or 0),
        "total_bytes": int(raw.get("total_bytes") or 0),
        "speed": float(raw.get("speed") or 0.0),
        "error": raw.get("error"),
        "failure_reason": raw.get("failure_reason"),
        "failure_detail": raw.get("failure_detail"),
        "retry_count": retry_count,
        "max_retries": max_retries,
        "terminal": 1 if terminal else 0,
        "created_at": str(raw.get("created_at") or now),
        "started_at": raw.get("started_at"),
        "completed_at": raw.get("completed_at"),
        "updated_at": str(raw.get("updated_at") or now),
    }


# ============= Search Routes =============

@router.get("/search", response_model=SearchResponse)
async def search_anime(q: str = Query(..., min_length=1, description="Search query")):
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    try:
        results = await animepahe_client.search(q)
        return SearchResponse(
            results=[AnimeSearchResult(
                session=r.session, title=r.title, type=r.type,
                episodes=r.episodes, status=r.status, season=r.season,
                year=r.year, score=r.score, poster=r.poster,
            ) for r in results],
            query=q, count=len(results),
        )
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.get("/search/posters")
async def get_mal_posters(titles: str = Query(..., description="Pipe-separated list of anime titles")):
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    title_list = [t.strip() for t in titles.split("|") if t.strip()]
    posters = await animepahe_client.get_mal_posters(title_list)
    return {"posters": posters}


# ============= Anime Routes =============

@router.get("/anime/{session}", response_model=AnimeDetails)
async def get_anime_details(session: str):
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    try:
        details = await animepahe_client.get_anime_details(session)
        return AnimeDetails(**details)
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get anime details: {e}")


@router.get("/anime/{session}/episodes", response_model=EpisodesResponse)
async def get_episodes(
    session: str,
    page: int = Query(default=1, ge=1),
    all_pages: bool = Query(default=False),
):
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    try:
        if all_pages:
            all_eps = await animepahe_client.get_all_episodes(session)
            return EpisodesResponse(
                anime_session=session,
                episodes=[Episode(
                    id=e.id, episode=e.episode, episode_display=e.episode_display,
                    title=e.title, snapshot=e.snapshot, duration=e.duration,
                    session=e.session, filler=e.filler, created_at=e.created_at,
                ) for e in all_eps],
                page=1, total_pages=1, total_episodes=len(all_eps),
            )
        else:
            episodes, total_pages = await animepahe_client.get_episodes(session, page)
            return EpisodesResponse(
                anime_session=session,
                episodes=[Episode(
                    id=e.id, episode=e.episode, episode_display=e.episode_display,
                    title=e.title, snapshot=e.snapshot, duration=e.duration,
                    session=e.session, filler=e.filler, created_at=e.created_at,
                ) for e in episodes],
                page=page, total_pages=total_pages, total_episodes=len(episodes),
            )
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get episodes: {e}")


# ============= Download Routes =============

@router.get("/episode/{anime_session}/{episode_session}/links", response_model=EpisodeLinksResponse)
async def get_episode_links(anime_session: str, episode_session: str):
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    try:
        options = await animepahe_client.get_episode_download_options(anime_session, episode_session)
        return EpisodeLinksResponse(
            anime_session=anime_session, episode_session=episode_session,
            options=[DownloadOption(
                pahe_link=o.pahe_link, quality=o.quality, resolution=o.resolution,
                audio=o.audio, size=o.size,
            ) for o in options],
        )
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get download links: {e}")


@router.post("/download")
async def start_download(request: DownloadRequest):
    if not animepahe_client or not download_manager:
        raise HTTPException(status_code=500, detail="Client not initialized")
    try:
        all_episodes = await animepahe_client.get_all_episodes(request.anime_session)
        episodes_to_download = [e for e in all_episodes if e.session in request.episodes]
        if not episodes_to_download:
            raise HTTPException(status_code=400, detail="No valid episodes found")

        async def process_and_queue():
            total = len(episodes_to_download)
            processed = 0
            try:
                link_errors: list[str] = []
                resolved_links: list[dict] = []
                for episode in episodes_to_download:
                    try:
                        options = await animepahe_client.get_episode_download_options(
                            request.anime_session,
                            episode.session,
                        )
                        if not options:
                            raise RuntimeError("No download options found")
                        selected = _select_download_option(options, request.resolution)
                        direct_link = await animepahe_client.get_direct_download_link(selected.pahe_link)
                        resolved_links.append(
                            {
                                "episode": episode.episode,
                                "session": episode.session,
                                "resolution": selected.resolution,
                                "direct_link": direct_link,
                            }
                        )
                    except Exception as e:
                        link_errors.append(str(e))
                    processed += 1
                    await broadcast_link_progress(processed, total)

                if resolved_links:
                    resolved_links.sort(key=lambda x: float(x.get("episode", 0)))

                added_count = 0
                for link_info in resolved_links:
                    task = await download_manager.add_task(
                        url=link_info["direct_link"],
                        anime_title=request.anime_title,
                        episode=link_info["episode"],
                        resolution=link_info["resolution"],
                        anime_session=request.anime_session,
                        episode_session=link_info.get("session"),
                    )
                    if task:
                        added_count += 1

                if added_count == 0 and link_errors:
                    first_error = link_errors[0]
                    reason, detail = classify_failure(first_error)
                    raise RuntimeError(f"No links resolved ({reason}): {detail}")

                await broadcast_status()
            except Exception as e:
                logger.error("Error processing download links: %s", e)
                await broadcast_link_error(str(e), request.anime_title)

        asyncio.create_task(process_and_queue())
        return {
            "status": "queued",
            "message": f"Started processing {len(episodes_to_download)} episodes",
            "added_count": 0,
            "tasks": [],
        }
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except PathSafetyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start download: {e}")


@router.post("/download/batch")
async def batch_download(request: BatchDownloadRequest):
    if not animepahe_client or not download_manager:
        raise HTTPException(status_code=500, detail="Client not initialized")
    try:
        all_episodes = await animepahe_client.get_all_episodes(request.anime_session)
        start = request.start_episode
        end = request.end_episode or len(all_episodes)
        episodes_to_download = [e for e in all_episodes if start <= e.episode <= end]
        if not episodes_to_download:
            raise HTTPException(status_code=400, detail="No episodes in specified range")

        links = []
        errors = []
        for episode in episodes_to_download:
            try:
                options = await animepahe_client.get_episode_download_options(
                    request.anime_session,
                    episode.session,
                )
                if not options:
                    raise RuntimeError("No download options found")
                selected = _select_download_option(options, request.resolution)
                direct_link = await animepahe_client.get_direct_download_link(selected.pahe_link)
                links.append(
                    {
                        "episode": episode.episode,
                        "session": episode.session,
                        "resolution": selected.resolution,
                        "direct_link": direct_link,
                    }
                )
            except Exception as e:
                errors.append({"episode": episode.episode, "error": str(e)})

        links.sort(key=lambda x: float(x.get("episode", 0)))
        added_tasks = []
        for link_info in links:
            task = await download_manager.add_task(
                url=link_info["direct_link"], anime_title=request.anime_title,
                episode=link_info["episode"], resolution=link_info["resolution"],
                anime_session=request.anime_session,
                episode_session=link_info.get("session"),
            )
            if task:
                added_tasks.append(download_manager._task_to_dict(task))
        await broadcast_status()
        return {
            "status": "queued", "added_count": len(added_tasks),
            "error_count": len(errors), "tasks": added_tasks, "errors": errors,
        }
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except PathSafetyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start batch download: {e}")


@router.get("/queue")
async def get_queue_status():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    status = download_manager.get_status()
    status["paused"] = download_manager.is_paused
    return status


@router.post("/queue/retry")
async def retry_failed():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    count = await download_manager.retry_failed()
    await broadcast_status()
    return {"retried_count": count}


@router.post("/queue/{task_id}/retry")
async def retry_single_task(task_id: str):
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    task = await download_manager.retry_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Failed or stopped task not found")
    await broadcast_status()
    return {"retried": True, "task": download_manager._task_to_dict(task)}


@router.post("/queue/{task_id}/re-resolve")
async def re_resolve_task(task_id: str):
    if not download_manager or not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")

    task = download_manager.find_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.anime_session or not task.episode_session:
        raise HTTPException(
            status_code=400,
            detail="Task is missing episode metadata required to re-resolve link",
        )

    try:
        options = await animepahe_client.get_episode_download_options(
            task.anime_session, task.episode_session,
        )
        selected = _select_download_option(options, task.resolution)
        direct_link = await animepahe_client.get_direct_download_link(selected.pahe_link)
        new_task = await download_manager.add_task(
            url=direct_link,
            anime_title=task.anime_title,
            episode=task.episode,
            resolution=selected.resolution,
            filename=task.filename,
            anime_session=task.anime_session,
            episode_session=task.episode_session,
        )
        if not new_task:
            raise HTTPException(status_code=409, detail="Task already queued or file already exists")
        await broadcast_status()
        return {"re_resolved": True, "task": download_manager._task_to_dict(new_task)}
    except HTTPException:
        raise
    except Exception as e:
        reason, detail = classify_failure(e)
        raise HTTPException(status_code=502, detail=f"Failed to re-resolve link ({reason}): {detail}")


@router.post("/queue/{task_id}/revalidate")
async def revalidate_task(task_id: str):
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")

    result = download_manager.revalidate_task_file(task_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=result.get("message", "Task not found"))
    await broadcast_status()
    return result


@router.post("/queue/clear")
async def clear_completed():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    count = download_manager.clear_completed()
    await broadcast_status()
    return {"cleared_count": count}


@router.delete("/queue/{task_id}")
async def cancel_download(task_id: str):
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    success = await download_manager.cancel_task(task_id)
    await broadcast_status()
    return {"success": success}


@router.delete("/queue")
async def cancel_all_downloads():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    count = await download_manager.cancel_all_tasks()
    await broadcast_status()
    return {"cancelled_count": count}


# ============= Queue Pause/Resume =============

@router.post("/queue/pause")
async def pause_queue():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    download_manager.pause()
    await broadcast_status()
    return {"paused": True}


@router.post("/queue/resume")
async def resume_queue():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    download_manager.resume()
    await broadcast_status()
    return {"paused": False}


# ============= Settings Routes =============

@router.get("/settings", response_model=AppSettings)
async def get_settings():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    res = app_config.default_resolution if app_config else 0
    return AppSettings(
        download_path=download_manager.download_path,
        max_workers=download_manager.max_workers,
        default_resolution=res,
    )


@router.put("/settings")
async def update_settings(request: UpdateSettingsRequest):
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")

    if request.download_path is not None:
        try:
            normalized = normalize_download_path(request.download_path)
        except PathSafetyError as e:
            raise HTTPException(status_code=400, detail=str(e))
        download_manager.set_download_path(normalized)

    if request.max_workers is not None:
        await download_manager.adjust_workers(request.max_workers)

    # Persist to config file
    if app_config:
        app_config.download_path = download_manager.download_path
        app_config.max_workers = download_manager.max_workers
        if request.default_resolution is not None:
            app_config.default_resolution = request.default_resolution
        save_config(app_config)

    result = AppSettings(
        download_path=download_manager.download_path,
        max_workers=download_manager.max_workers,
        default_resolution=app_config.default_resolution if app_config else 0,
    )
    await broadcast_settings()
    return result


# ============= Diagnostics / Maintenance =============

@router.get("/diagnostics")
async def get_diagnostics(request: Request):
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")

    startup_checks = getattr(request.app.state, "startup_checks", {})
    started_at = getattr(request.app.state, "started_at", None)
    health = build_health_payload(download_manager, startup_checks=startup_checks, started_at=started_at)
    environment_checks = await run_environment_checks(download_manager.download_path)
    recent_errors = collect_recent_errors(download_manager.failed_tasks, limit=20)

    return {
        "health": health,
        "metrics": download_manager.get_metrics(),
        "environment_checks": environment_checks,
        "recent_errors": recent_errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/backup/export")
async def export_backup():
    return {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "settings": state_store.load_settings(),
        "tasks": state_store.load_download_tasks(),
    }


@router.post("/backup/import")
async def import_backup(payload: dict = Body(...)):
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid backup payload")
    if download_manager.active_tasks:
        raise HTTPException(status_code=409, detail="Stop active downloads before importing backup")

    replace_existing = bool(payload.get("replace_existing", True))
    settings_payload = payload.get("settings", {})
    tasks_payload = payload.get("tasks", [])

    if settings_payload and not isinstance(settings_payload, dict):
        raise HTTPException(status_code=400, detail="Invalid settings payload")
    if tasks_payload and not isinstance(tasks_payload, list):
        raise HTTPException(status_code=400, detail="Invalid tasks payload")

    existing_settings = state_store.load_settings()
    merged_settings = dict(existing_settings)
    if settings_payload:
        merged_settings.update(settings_payload)

    if replace_existing:
        state_store.replace_settings(merged_settings)
    elif settings_payload:
        state_store.save_settings(settings_payload)

    normalized_tasks = [_normalize_import_task(task) for task in tasks_payload if isinstance(task, dict)]
    if replace_existing:
        state_store.replace_download_tasks(normalized_tasks)
    elif normalized_tasks:
        state_store.upsert_download_tasks(normalized_tasks)

    # Apply runtime settings from imported data.
    imported_download_path = merged_settings.get("download_path")
    imported_max_workers = merged_settings.get("max_workers")
    imported_default_resolution = merged_settings.get("default_resolution")

    if imported_download_path:
        try:
            normalized_path = normalize_download_path(str(imported_download_path))
            download_manager.set_download_path(normalized_path)
            if app_config:
                app_config.download_path = normalized_path
        except PathSafetyError as e:
            raise HTTPException(status_code=400, detail=f"Invalid imported download_path: {e}")

    if imported_max_workers is not None:
        await download_manager.adjust_workers(int(imported_max_workers))
        if app_config:
            app_config.max_workers = int(imported_max_workers)

    if imported_default_resolution is not None and app_config:
        app_config.default_resolution = int(imported_default_resolution)

    if app_config:
        save_config(app_config)

    await download_manager.reload_state_from_store()
    await broadcast_settings()
    await broadcast_status()

    return {
        "imported": True,
        "replace_existing": replace_existing,
        "settings_imported": bool(settings_payload),
        "tasks_imported": len(normalized_tasks),
    }


@router.post("/maintenance/cleanup")
async def cleanup_maintenance():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    if download_manager.active_tasks:
        raise HTTPException(status_code=409, detail="Stop active downloads before running cleanup")

    stale_files_removed = await download_manager.cleanup_stale_partials()
    orphan_entries_removed = await download_manager.cleanup_orphan_queue_entries()
    await download_manager.reload_state_from_store()
    await broadcast_status()

    return {
        "stale_files_removed": stale_files_removed,
        "orphan_queue_entries_removed": orphan_entries_removed,
    }


# ============= Open Folder =============

@router.get("/settings/open-folder")
async def open_download_folder():
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    path = download_manager.download_path
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Download folder does not exist")
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return {"opened": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {e}")


# ============= WebSocket =============

@router.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.add(websocket)
    try:
        if download_manager:
            status = download_manager.get_status()
            status["paused"] = download_manager.is_paused
            await websocket.send_json({"type": "status", "queue": status})
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        connected_websockets.discard(websocket)
