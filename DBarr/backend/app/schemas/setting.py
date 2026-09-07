from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class AppSettings(BaseModel):
    ollama_url: str = "http://localhost:11434"
    ollama_primary_model: str = "llama3.1:8b"
    ollama_fallback_models: List[str] = ["qwen2.5:7b", "mistral:7b"]
    ollama_fallback_model: str = "qwen2.5:7b"
    
    sonarr_url: str = "http://localhost:8989"
    sonarr_api_key: str = ""
    
    opensubtitles_api_key: str = ""
    opensubtitles_user_agent: str = "DBarr v0.1"
    subdl_api_key: str = ""
    
    tmdb_api_key: str = ""
    omdb_api_key: str = ""
    
    max_concurrent_jobs: int = 2
    max_concurrent_ollama_requests: int = 1
    default_language: str = "en"


class SettingUpdate(BaseModel):
    settings: Dict[str, Any]


class ConnectionTestRequest(BaseModel):
    service: str  # sonarr, ollama, opensubtitles, subdl, tmdb, omdb
    url: Optional[str] = None
    api_key: Optional[str] = None
    user_agent: Optional[str] = None
    model: Optional[str] = None


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    available_models: Optional[List[str]] = None
    details: Optional[Dict[str, Any]] = None
