from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class AppSettings(BaseModel):
    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_primary_model: str = "gemma4:e2b"
    ollama_fallback_models: List[str] = ["Gemma-4-E2B-it-uncensored-GGUF:Q4_K_M"]
    ollama_fallback_model: str = "Gemma-4-E2B-it-uncensored-GGUF:Q4_K_M"
    
    # Sonarr
    sonarr_url: str = ""
    sonarr_api_key: str = ""
    
    # Metadata Providers
    tmdb_api_key: str = ""
    tvmaze_api_key: str = ""
    omdb_api_key: str = ""
    
    # Transcript Providers
    subdl_api_key: str = ""
    opensubtitles_api_key: str = ""
    opensubtitles_user_agent: str = "DBarr v0.1"

    # Concurrency & Resource Limits (defaults all 1)
    max_concurrent_jobs: int = 1
    max_concurrent_ollama_requests: int = 1
    default_language: str = "en"

    model_config = ConfigDict(from_attributes=True)


class SettingUpdate(BaseModel):
    settings: Dict[str, Any]


class ConnectionTestRequest(BaseModel):
    service: str  # sonarr, ollama, tmdb, tvmaze, omdb, subdl, opensubtitles
    config: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    api_key: Optional[str] = None
    user_agent: Optional[str] = None
    model: Optional[str] = None


class ConnectionTestResponse(BaseModel):
    service: str = ""
    success: bool
    message: str
    available_models: Optional[List[str]] = None
    details: Optional[Dict[str, Any]] = None
