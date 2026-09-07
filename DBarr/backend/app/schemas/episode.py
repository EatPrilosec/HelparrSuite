from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TranscriptResponse(BaseModel):
    id: int
    episode_id: int
    language: str
    is_native_language: bool
    source_provider: str
    preview_text: Optional[str] = None
    raw_content: Optional[str] = None
    dialogue_anchors: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EpisodeSourceMetadataResponse(BaseModel):
    id: int
    episode_id: int
    show_id: int
    source_name: str
    source_season_number: Optional[int] = None
    source_episode_number: Optional[int] = None
    source_absolute_number: Optional[int] = None
    title: Optional[str] = None
    overview: Optional[str] = None
    air_date: Optional[str] = None
    runtime_mins: Optional[int] = None
    match_method: str
    match_confidence: float
    llm_reasoning: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EpisodeResponse(BaseModel):
    id: int
    show_id: int
    sonarr_episode_id: int
    season_number: int
    episode_number: int
    absolute_episode_number: Optional[int] = None
    title: str
    overview: Optional[str] = None
    air_date: Optional[str] = None
    runtime_mins: Optional[int] = None
    has_file: bool
    monitored: bool
    ai_verification_status: str
    ai_confidence_score: float
    ai_audit_notes: Optional[str] = None
    transcripts: List[TranscriptResponse] = []
    source_variations: List[EpisodeSourceMetadataResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
