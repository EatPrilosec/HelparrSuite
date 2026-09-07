from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from backend.app.schemas.episode import EpisodeResponse


class SonarrShowLookup(BaseModel):
    sonarr_series_id: int
    title: str
    sort_title: Optional[str] = None
    year: Optional[int] = None
    status: Optional[str] = None
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    original_language: Optional[str] = "English"
    season_count: int = 0
    episode_count: int = 0
    monitored: bool = True
    tvdb_id: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    path: Optional[str] = None
    already_imported: bool = False


class ShowImportRequest(BaseModel):
    sonarr_series_id: int
    scan_mode: str = "full"  # full, metadata_only, transcripts_only


class BatchImportRequest(BaseModel):
    series_ids: List[int]
    scan_mode: str = "full"


class ShowBriefResponse(BaseModel):
    id: int
    sonarr_series_id: int
    title: str
    year: Optional[int] = None
    status: Optional[str] = None
    poster_url: Optional[str] = None
    original_language: Optional[str] = "English"
    audit_status: str
    monitored: bool
    tvdb_id: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    tvmaze_id: Optional[int] = None
    episode_count: int = 0
    verified_episode_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShowResponse(BaseModel):
    id: int
    sonarr_series_id: int
    title: str
    clean_title: Optional[str] = None
    sort_title: Optional[str] = None
    original_title: Optional[str] = None
    year: Optional[int] = None
    status: Optional[str] = None
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    original_language: Optional[str] = "English"
    path: Optional[str] = None
    monitored: bool
    tvdb_id: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    tvmaze_id: Optional[int] = None
    audit_status: str
    last_audited_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    episodes: List[EpisodeResponse] = []

    model_config = ConfigDict(from_attributes=True)
