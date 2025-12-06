"""
Pydantic models for API request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ============= Search Models =============

class AnimeSearchResult(BaseModel):
    """Search result from AnimePahe"""
    session: str
    title: str
    type: str = "TV"
    episodes: int = 0
    status: str = "Unknown"
    season: str = "Unknown"
    year: int = 0
    score: float = 0.0
    poster: str = ""


class SearchResponse(BaseModel):
    """Response for search endpoint"""
    results: list[AnimeSearchResult]
    query: str
    count: int


# ============= Anime Details Models =============

class AnimeDetails(BaseModel):
    """Detailed anime information"""
    session: str
    title: str
    total_episodes: int
    last_page: int
    per_page: int = 30
    # MAL Details
    synopsis: str = ""
    score: float = 0.0
    status: str = ""
    aired: str = ""
    genres: list[str] = []
    english_title: str = ""
    japanese_title: str = ""
    poster: str = ""


class Episode(BaseModel):
    """Episode information"""
    id: int
    episode: float
    episode_display: str
    title: str = ""
    snapshot: str = ""
    duration: str = ""
    session: str
    filler: bool = False
    created_at: str = ""


class EpisodesResponse(BaseModel):
    """Response for episodes endpoint"""
    anime_session: str
    episodes: list[Episode]
    page: int
    total_pages: int
    total_episodes: int


# ============= Download Models =============

class DownloadOption(BaseModel):
    """Available download option for an episode"""
    pahe_link: str
    quality: str
    resolution: int
    audio: str = "jpn"
    size: str = ""


class EpisodeLinksResponse(BaseModel):
    """Response for episode download links"""
    anime_session: str
    episode_session: str
    options: list[DownloadOption]


class DownloadRequest(BaseModel):
    """Request to start downloading episodes"""
    anime_session: str
    anime_title: str
    episodes: list[str]  # List of episode session IDs
    resolution: int = Field(default=0, description="0=highest, -1=lowest, or specific like 720")


class BatchDownloadRequest(BaseModel):
    """Request to batch download a range of episodes"""
    anime_session: str
    anime_title: str
    start_episode: int = 1
    end_episode: Optional[int] = None  # None = all episodes
    resolution: int = Field(default=0, description="0=highest, -1=lowest, or specific like 720")


class DownloadProgress(BaseModel):
    """Progress update for a download"""
    id: str
    filename: str
    anime_title: str
    episode: float
    resolution: int
    status: str
    progress: float
    downloaded_bytes: int
    total_bytes: int
    speed: float
    error: Optional[str] = None


class DownloadQueueStatus(BaseModel):
    """Current status of download queue"""
    running: bool
    max_workers: int
    pending_count: int
    active_count: int
    completed_count: int
    failed_count: int
    active: list[DownloadProgress]
    pending: list[DownloadProgress]
    completed: list[DownloadProgress]
    failed: list[DownloadProgress]


# ============= Settings Models =============

class AppSettings(BaseModel):
    """Application settings"""
    download_path: str
    max_workers: int = 4
    default_resolution: int = 0  # 0=highest


class UpdateSettingsRequest(BaseModel):
    """Request to update settings"""
    download_path: Optional[str] = None
    max_workers: Optional[int] = Field(default=None, ge=1, le=8)
    default_resolution: Optional[int] = None


# ============= WebSocket Messages =============

class WSMessage(BaseModel):
    """WebSocket message wrapper"""
    type: str  # progress, status, error, settings
    data: dict


class WSProgressUpdate(BaseModel):
    """WebSocket progress update"""
    type: str = "progress"
    task: DownloadProgress


class WSStatusUpdate(BaseModel):
    """WebSocket status update"""
    type: str = "status"
    queue: DownloadQueueStatus


class WSError(BaseModel):
    """WebSocket error message"""
    type: str = "error"
    message: str
    details: Optional[str] = None
