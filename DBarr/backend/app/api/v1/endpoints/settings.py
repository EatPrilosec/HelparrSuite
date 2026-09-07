import json
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.database import get_db
from backend.app.models.setting import Setting
from backend.app.schemas.setting import AppSettings, SettingUpdate, ConnectionTestRequest, ConnectionTestResponse
from backend.app.services.ollama_client import OllamaClient
from backend.app.services.sonarr_client import SonarrClient
from backend.app.services.concurrency_manager import concurrency_manager

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettings)
async def get_settings(db: AsyncSession = Depends(get_db)):
    stmt = select(Setting)
    res = await db.execute(stmt)
    records = res.scalars().all()
    data = {r.key: r.value for r in records}

    max_jobs = int(data.get("max_concurrent_jobs", 2)) if str(data.get("max_concurrent_jobs", "")).isdigit() else 2
    max_ollama = int(data.get("max_concurrent_ollama_requests", 1)) if str(data.get("max_concurrent_ollama_requests", "")).isdigit() else 1
    concurrency_manager.update_limits(max_jobs, max_ollama)

    # Parse fallback models
    fallback_models: List[str] = []
    raw_fallbacks = data.get("ollama_fallback_models")
    if raw_fallbacks:
        try:
            parsed = json.loads(raw_fallbacks)
            if isinstance(parsed, list):
                fallback_models = [str(m).strip() for m in parsed if str(m).strip()]
        except Exception:
            fallback_models = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]

    if not fallback_models and data.get("ollama_fallback_model"):
        fallback_models = [data["ollama_fallback_model"].strip()]

    if not fallback_models:
        fallback_models = ["qwen2.5:7b", "mistral:7b"]

    return AppSettings(
        ollama_url=data.get("ollama_url", "http://localhost:11434"),
        ollama_primary_model=data.get("ollama_primary_model", "llama3.1:8b"),
        ollama_fallback_models=fallback_models,
        ollama_fallback_model=fallback_models[0],
        sonarr_url=data.get("sonarr_url", "http://localhost:8989"),
        sonarr_api_key=data.get("sonarr_api_key", ""),
        opensubtitles_api_key=data.get("opensubtitles_api_key", ""),
        opensubtitles_user_agent=data.get("opensubtitles_user_agent", "DBarr v0.1"),
        subdl_api_key=data.get("subdl_api_key", ""),
        tmdb_api_key=data.get("tmdb_api_key", ""),
        omdb_api_key=data.get("omdb_api_key", ""),
        max_concurrent_jobs=max_jobs,
        max_concurrent_ollama_requests=max_ollama,
        default_language=data.get("default_language", "en")
    )


@router.post("")
async def update_settings(payload: SettingUpdate, db: AsyncSession = Depends(get_db)):
    for key, value in payload.settings.items():
        if isinstance(value, (list, dict)):
            value_str = json.dumps(value)
        else:
            value_str = str(value) if value is not None else ""

        res = await db.execute(select(Setting).where(Setting.key == key))
        setting = res.scalars().first()
        if setting:
            setting.value = value_str
        else:
            setting = Setting(key=key, value=value_str)
            db.add(setting)

    await db.commit()
    return {"success": True, "message": "Settings updated successfully"}


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(req: ConnectionTestRequest, db: AsyncSession = Depends(get_db)):
    # Fallback to stored values if request params are omitted
    stmt = select(Setting)
    res = await db.execute(stmt)
    records = {r.key: r.value for r in res.scalars().all()}

    if req.service == "sonarr":
        url = req.url or records.get("sonarr_url", "http://localhost:8989")
        api_key = req.api_key or records.get("sonarr_api_key", "")
        if not api_key:
            return ConnectionTestResponse(success=False, message="Sonarr API key is not configured")
        result = await SonarrClient.test_connection(url, api_key)
        return ConnectionTestResponse(**result)

    elif req.service == "ollama":
        url = req.url or records.get("ollama_url", "http://localhost:11434")
        result = await OllamaClient.test_connection(url)
        return ConnectionTestResponse(**result)

    raise HTTPException(status_code=400, detail=f"Unsupported service test: {req.service}")
