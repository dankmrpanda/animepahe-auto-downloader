"""
API Routes for AnimePahe Web Downloader
"""

import os
import asyncio
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from typing import Optional

from api.models import (
    SearchResponse, AnimeSearchResult, AnimeDetails, Episode,
    EpisodesResponse, EpisodeLinksResponse, DownloadOption,
    DownloadRequest, BatchDownloadRequest, DownloadQueueStatus,
    AppSettings, UpdateSettingsRequest, DownloadProgress
)
from core.animepahe import AnimePaheClient, AnimePaheError
from core.downloader import DownloadManager, DownloadTask


router = APIRouter(prefix="/api", tags=["api"])

# Initialize clients (will be set by main.py)
animepahe_client: Optional[AnimePaheClient] = None
download_manager: Optional[DownloadManager] = None

# WebSocket connections for progress updates
connected_websockets: set[WebSocket] = set()


def init_clients(client: AnimePaheClient, manager: DownloadManager):
    """Initialize the API clients"""
    global animepahe_client, download_manager
    animepahe_client = client
    download_manager = manager
    
    # Add progress callback
    async def progress_callback(task: DownloadTask):
        await broadcast_progress(task)
    
    download_manager.add_progress_callback(progress_callback)


async def broadcast_progress(task: DownloadTask):
    """Broadcast download progress to all connected WebSocket clients"""
    if not connected_websockets:
        return
    
    message = {
        "type": "progress",
        "task": download_manager._task_to_dict(task)
    }
    
    disconnected = set()
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.add(ws)
    
    # Clean up disconnected clients
    connected_websockets.difference_update(disconnected)


async def broadcast_status():
    """Broadcast full queue status to all connected clients"""
    if not connected_websockets or not download_manager:
        return
    
    message = {
        "type": "status",
        "queue": download_manager.get_status()
    }
    
    disconnected = set()
    for ws in connected_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.add(ws)
    
    connected_websockets.difference_update(disconnected)


# ============= Search Routes =============

@router.get("/search", response_model=SearchResponse)
async def search_anime(q: str = Query(..., min_length=1, description="Search query")):
    """
    Search for anime by name.
    Returns a list of matching anime with basic info.
    """
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    
    try:
        results = await animepahe_client.search(q)
        return SearchResponse(
            results=[AnimeSearchResult(
                session=r.session,
                title=r.title,
                type=r.type,
                episodes=r.episodes,
                status=r.status,
                season=r.season,
                year=r.year,
                score=r.score,
                poster=r.poster,
            ) for r in results],
            query=q,
            count=len(results)
        )
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ============= Anime Routes =============

@router.get("/anime/{session}", response_model=AnimeDetails)
async def get_anime_details(session: str):
    """
    Get detailed information about an anime.
    """
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    
    try:
        details = await animepahe_client.get_anime_details(session)
        return AnimeDetails(**details)
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get anime details: {str(e)}")


@router.get("/anime/{session}/episodes", response_model=EpisodesResponse)
async def get_episodes(
    session: str,
    page: int = Query(default=1, ge=1),
    all_pages: bool = Query(default=False, description="Fetch all episodes at once")
):
    """
    Get episodes for an anime.
    Supports pagination (30 per page) or fetching all at once.
    """
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    
    try:
        if all_pages:
            all_episodes = await animepahe_client.get_all_episodes(session)
            return EpisodesResponse(
                anime_session=session,
                episodes=[Episode(
                    id=e.id,
                    episode=e.episode,
                    episode_display=e.episode_display,
                    title=e.title,
                    snapshot=e.snapshot,
                    duration=e.duration,
                    session=e.session,
                    filler=e.filler,
                    created_at=e.created_at,
                ) for e in all_episodes],
                page=1,
                total_pages=1,
                total_episodes=len(all_episodes)
            )
        else:
            episodes, total_pages = await animepahe_client.get_episodes(session, page)
            return EpisodesResponse(
                anime_session=session,
                episodes=[Episode(
                    id=e.id,
                    episode=e.episode,
                    episode_display=e.episode_display,
                    title=e.title,
                    snapshot=e.snapshot,
                    duration=e.duration,
                    session=e.session,
                    filler=e.filler,
                    created_at=e.created_at,
                ) for e in episodes],
                page=page,
                total_pages=total_pages,
                total_episodes=len(episodes)  # This is per page; use /anime/{session} for total
            )
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get episodes: {str(e)}")


# ============= Download Routes =============

@router.get("/episode/{anime_session}/{episode_session}/links", response_model=EpisodeLinksResponse)
async def get_episode_links(anime_session: str, episode_session: str):
    """
    Get available download options for a specific episode.
    """
    if not animepahe_client:
        raise HTTPException(status_code=500, detail="Client not initialized")
    
    try:
        options = await animepahe_client.get_episode_download_options(
            anime_session, 
            episode_session
        )
        return EpisodeLinksResponse(
            anime_session=anime_session,
            episode_session=episode_session,
            options=[DownloadOption(
                pahe_link=o.pahe_link,
                quality=o.quality,
                resolution=o.resolution,
                audio=o.audio,
                size=o.size,
            ) for o in options]
        )
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get download links: {str(e)}")


@router.post("/download")
async def start_download(request: DownloadRequest):
    """
    Start downloading specific episodes.
    Episodes are added to the download queue.
    """
    if not animepahe_client or not download_manager:
        raise HTTPException(status_code=500, detail="Client not initialized")
    
    try:
        # Get all episodes first
        all_episodes = await animepahe_client.get_all_episodes(request.anime_session)
        
        # Filter to requested episodes
        episodes_to_download = [
            e for e in all_episodes 
            if e.session in request.episodes
        ]
        
        if not episodes_to_download:
            raise HTTPException(status_code=400, detail="No valid episodes found")
        
        # Get download links for each episode
        # We process them in batches but add to queue immediately
        
        # Create a background task to process links and add to queue
        async def process_and_queue():
            # Process episodes in chunks to avoid overwhelming the server
            chunk_size = 5
            for i in range(0, len(episodes_to_download), chunk_size):
                chunk = episodes_to_download[i:i + chunk_size]
                
                # Get links for this chunk
                links = await animepahe_client.get_episode_links_batch(
                    request.anime_session,
                    chunk,
                    request.resolution
                )
                
                # Add to download queue immediately
                for link_info in links:
                    if link_info.get("error"):
                        continue
                    
                    await download_manager.add_task(
                        url=link_info["direct_link"],
                        anime_title=request.anime_title,
                        episode=link_info["episode"],
                        resolution=link_info["resolution"],
                    )
                
                # Broadcast status update
                await broadcast_status()

        # Start processing in background
        asyncio.create_task(process_and_queue())
        
        return {
            "status": "queued",
            "message": f"Started processing {len(episodes_to_download)} episodes",
            "added_count": 0, # Will be updated via WebSocket
            "tasks": []
        }
        
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start download: {str(e)}")


@router.post("/download/batch")
async def batch_download(request: BatchDownloadRequest):
    """
    Download a range of episodes.
    """
    if not animepahe_client or not download_manager:
        raise HTTPException(status_code=500, detail="Client not initialized")
    
    try:
        # Get all episodes
        all_episodes = await animepahe_client.get_all_episodes(request.anime_session)
        
        # Filter by range
        start = request.start_episode
        end = request.end_episode or len(all_episodes)
        
        episodes_to_download = [
            e for e in all_episodes 
            if start <= e.episode <= end
        ]
        
        if not episodes_to_download:
            raise HTTPException(status_code=400, detail="No episodes in specified range")
        
        # Get download links
        links = await animepahe_client.get_episode_links_batch(
            request.anime_session,
            episodes_to_download,
            request.resolution
        )
        
        # Add to queue
        added_tasks = []
        errors = []
        
        for link_info in links:
            if link_info.get("error"):
                errors.append({
                    "episode": link_info.get("episode"),
                    "error": link_info.get("error")
                })
                continue
            
            task = await download_manager.add_task(
                url=link_info["direct_link"],
                anime_title=request.anime_title,
                episode=link_info["episode"],
                resolution=link_info["resolution"],
            )
            added_tasks.append(download_manager._task_to_dict(task))
        
        await broadcast_status()
        
        return {
            "status": "queued",
            "added_count": len(added_tasks),
            "error_count": len(errors),
            "tasks": added_tasks,
            "errors": errors
        }
        
    except AnimePaheError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start batch download: {str(e)}")


@router.get("/queue", response_model=DownloadQueueStatus)
async def get_queue_status():
    """
    Get current download queue status.
    """
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    
    return download_manager.get_status()


@router.post("/queue/retry")
async def retry_failed():
    """
    Retry all failed downloads.
    """
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    
    count = await download_manager.retry_failed()
    await broadcast_status()
    
    return {"retried_count": count}


@router.post("/queue/clear")
async def clear_completed():
    """
    Clear completed downloads from history.
    """
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    
    count = download_manager.clear_completed()
    await broadcast_status()
    
    return {"cleared_count": count}


@router.delete("/queue/{task_id}")
async def cancel_download(task_id: str):
    """
    Cancel a pending or active download.
    """
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    
    success = await download_manager.cancel_task(task_id)
    await broadcast_status()
    
    return {"success": success}


# ============= Settings Routes =============

@router.get("/settings", response_model=AppSettings)
async def get_settings():
    """
    Get current application settings.
    """
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    
    return AppSettings(
        download_path=download_manager.download_path,
        max_workers=download_manager.max_workers,
        default_resolution=0  # Could be stored in a config file
    )


@router.put("/settings")
async def update_settings(request: UpdateSettingsRequest):
    """
    Update application settings.
    """
    if not download_manager:
        raise HTTPException(status_code=500, detail="Download manager not initialized")
    
    if request.download_path is not None:
        # Validate path
        if not os.path.isabs(request.download_path):
            raise HTTPException(status_code=400, detail="Download path must be absolute")
        
        # Create if doesn't exist
        os.makedirs(request.download_path, exist_ok=True)
        download_manager.set_download_path(request.download_path)
    
    if request.max_workers is not None:
        download_manager.max_workers = request.max_workers
    
    return AppSettings(
        download_path=download_manager.download_path,
        max_workers=download_manager.max_workers,
        default_resolution=request.default_resolution or 0
    )


# ============= WebSocket =============

@router.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """
    WebSocket endpoint for real-time download progress updates.
    """
    await websocket.accept()
    connected_websockets.add(websocket)
    
    try:
        # Send initial status
        if download_manager:
            await websocket.send_json({
                "type": "status",
                "queue": download_manager.get_status()
            })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                
                # Handle ping/pong for connection keep-alive
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
                
    except WebSocketDisconnect:
        pass
    finally:
        connected_websockets.discard(websocket)
