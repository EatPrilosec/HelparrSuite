import json
from typing import Dict, Any, List, Union
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.database import get_db
from backend.app.models.setting import Setting
from backend.app.schemas.setting import AppSettings, SettingUpdate, ConnectionTestRequest, ConnectionTestResponse
from backend.app.services.ollama_client import OllamaClient
from backend.app.services.sonarr_client import SonarrClient
from backend.app.services.tmdb_client import TMDBClient
from backend.app.services.tvmaze_client import TVmazeClient
from backend.app.services.omdb_client import OMDbClient
from backend.app.services.subdl_client import SubDLClient
from backend.app.services.opensubtitles_client import OpenSubtitlesClient
from backend.app.core.config_manager import read_config_file, write_config_file, get_env_overrides
from backend.app.services.concurrency_manager import concurrency_manager

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettings)
async def get_settings(db: AsyncSession = Depends(get_db)):
    stmt = select(Setting)
    res = await db.execute(stmt)
    records = res.scalars().all()
    data = {r.key: r.value for r in records}

    # Merge file config and env config for any empty/missing values
    file_cfg = read_config_file()
    env_cfg = get_env_overrides()
    for k, v in {**file_cfg, **env_cfg}.items():
        if not data.get(k) and v is not None and str(v).strip():
            data[k] = json.dumps(v) if isinstance(v, (list, dict)) else str(v)

    max_jobs = int(data.get("max_concurrent_jobs", 1)) if str(data.get("max_concurrent_jobs", "")).isdigit() else 1
    max_ollama = int(data.get("max_concurrent_ollama_requests", 1)) if str(data.get("max_concurrent_ollama_requests", "")).isdigit() else 1
    batch_size = int(data.get("ai_batch_size", 1)) if str(data.get("ai_batch_size", "")).isdigit() else 1

    concurrency_manager.update_limits(max_jobs, max_ollama)

    # Parse fallback models
    fallback_models: List[str] = []
    raw_fallbacks = data.get("ollama_fallback_models")
    if raw_fallbacks:
        try:
            parsed = json.loads(raw_fallbacks) if isinstance(raw_fallbacks, str) else raw_fallbacks
            if isinstance(parsed, list):
                fallback_models = [str(m).strip() for m in parsed if str(m).strip()]
        except Exception:
            if isinstance(raw_fallbacks, str):
                fallback_models = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]

    if not fallback_models and data.get("ollama_fallback_model"):
        fallback_models = [str(data["ollama_fallback_model"]).strip()]

    if not fallback_models:
        fallback_models = ["Gemma-4-E2B-it-uncensored-GGUF:Q4_K_M"]

    primary_model = data.get("ollama_primary_model", "gemma4:e2b")

    return AppSettings(
        ollama_url=data.get("ollama_url", "http://localhost:11434"),
        ollama_primary_model=primary_model,
        ollama_fallback_models=fallback_models,
        ollama_fallback_model=fallback_models[0],
        ai_batch_size=max(1, batch_size),
        sonarr_url=data.get("sonarr_url", ""),
        sonarr_api_key=data.get("sonarr_api_key", ""),
        tmdb_api_key=data.get("tmdb_api_key", ""),
        tvmaze_api_key=data.get("tvmaze_api_key", ""),
        omdb_api_key=data.get("omdb_api_key", ""),
        subdl_api_key=data.get("subdl_api_key", ""),
        opensubtitles_api_key=data.get("opensubtitles_api_key", ""),
        opensubtitles_user_agent=data.get("opensubtitles_user_agent", "DBarr v0.1"),
        max_concurrent_jobs=max_jobs,
        max_concurrent_ollama_requests=max_ollama,
        default_language=data.get("default_language", "en")
    )


@router.post("", response_model=AppSettings)
async def update_settings(payload: Union[AppSettings, SettingUpdate, Dict[str, Any]], db: AsyncSession = Depends(get_db)):
    if isinstance(payload, SettingUpdate):
        raw_dict = payload.settings
    elif isinstance(payload, dict):
        raw_dict = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
    elif hasattr(payload, "model_dump"):
        raw_dict = payload.model_dump()
        if "settings" in raw_dict and isinstance(raw_dict["settings"], dict):
            raw_dict = raw_dict["settings"]
    else:
        raw_dict = {}

    PROTECTED_KEYS = {
        "sonarr_api_key",
        "tmdb_api_key",
        "tvmaze_api_key",
        "omdb_api_key",
        "subdl_api_key",
        "opensubtitles_api_key",
        "sonarr_url",
    }

    # Fetch existing DB settings as baseline
    stmt = select(Setting)
    res = await db.execute(stmt)
    records = res.scalars().all()
    merged = {r.key: r.value for r in records}

    # Merge file and env config for baseline
    file_cfg = read_config_file()
    env_cfg = get_env_overrides()
    for k, v in {**file_cfg, **env_cfg}.items():
        if not merged.get(k) and v is not None and str(v).strip():
            merged[k] = json.dumps(v) if isinstance(v, (list, dict)) else str(v)

    # Apply incoming updates
    for k, v in raw_dict.items():
        if v is None:
            continue
        val_str = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
        # If incoming value is empty/blank for a protected key, do NOT overwrite existing non-empty value
        if k in PROTECTED_KEYS and not val_str.strip():
            if merged.get(k) and str(merged[k]).strip():
                continue
        merged[k] = val_str

    # Process and clean fallback models
    clean_fallbacks: List[str] = []
    raw_fallbacks = merged.get("ollama_fallback_models")
    if raw_fallbacks:
        try:
            parsed = json.loads(raw_fallbacks) if isinstance(raw_fallbacks, str) else raw_fallbacks
            if isinstance(parsed, list):
                clean_fallbacks = [str(m).strip() for m in parsed if str(m).strip()]
        except Exception:
            if isinstance(raw_fallbacks, str):
                clean_fallbacks = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]

    if not clean_fallbacks and merged.get("ollama_fallback_model"):
        clean_fallbacks = [str(merged["ollama_fallback_model"]).strip()]

    if not clean_fallbacks:
        clean_fallbacks = ["Gemma-4-E2B-it-uncensored-GGUF:Q4_K_M"]

    merged["ollama_fallback_models"] = json.dumps(clean_fallbacks)
    merged["ollama_fallback_model"] = clean_fallbacks[0]

    # Process concurrency and batch limits
    max_jobs = int(merged.get("max_concurrent_jobs", 1)) if str(merged.get("max_concurrent_jobs", "")).isdigit() else 1
    max_ollama = int(merged.get("max_concurrent_ollama_requests", 1)) if str(merged.get("max_concurrent_ollama_requests", "")).isdigit() else 1
    batch_size = int(merged.get("ai_batch_size", 1)) if str(merged.get("ai_batch_size", "")).isdigit() else 1

    merged["max_concurrent_jobs"] = str(max(1, max_jobs))
    merged["max_concurrent_ollama_requests"] = str(max(1, max_ollama))
    merged["ai_batch_size"] = str(max(1, batch_size))

    # Persist all merged settings to DB
    for k, val_str in merged.items():
        stmt_item = select(Setting).where(Setting.key == k)
        res_item = await db.execute(stmt_item)
        record = res_item.scalars().first()
        if record:
            record.value = val_str
        else:
            db.add(Setting(key=k, value=val_str))

    await db.commit()
    concurrency_manager.update_limits(max(1, max_jobs), max(1, max_ollama))

    # Build response object and write clean JSON to file
    response_settings = AppSettings(
        ollama_url=merged.get("ollama_url", "http://localhost:11434"),
        ollama_primary_model=merged.get("ollama_primary_model", "gemma4:e2b"),
        ollama_fallback_models=clean_fallbacks,
        ollama_fallback_model=clean_fallbacks[0],
        ai_batch_size=max(1, batch_size),
        sonarr_url=merged.get("sonarr_url", ""),
        sonarr_api_key=merged.get("sonarr_api_key", ""),
        tmdb_api_key=merged.get("tmdb_api_key", ""),
        tvmaze_api_key=merged.get("tvmaze_api_key", ""),
        omdb_api_key=merged.get("omdb_api_key", ""),
        subdl_api_key=merged.get("subdl_api_key", ""),
        opensubtitles_api_key=merged.get("opensubtitles_api_key", ""),
        opensubtitles_user_agent=merged.get("opensubtitles_user_agent", "DBarr v0.1"),
        max_concurrent_jobs=max(1, max_jobs),
        max_concurrent_ollama_requests=max(1, max_ollama),
        default_language=merged.get("default_language", "en"),
    )

    write_config_file(response_settings.model_dump())
    return response_settings


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(req: ConnectionTestRequest, db: AsyncSession = Depends(get_db)):
    svc = req.service.lower()
    cfg = req.config or {}

    # Merge top-level request fields if config map is omitted
    if not cfg:
        cfg = {
            "url": req.url,
            "api_key": req.api_key,
            "user_agent": req.user_agent,
            "model": req.model,
            "ollama_url": req.url,
            "sonarr_url": req.url,
            "sonarr_api_key": req.api_key,
            "tmdb_api_key": req.api_key,
            "omdb_api_key": req.api_key,
            "subdl_api_key": req.api_key,
            "opensubtitles_api_key": req.api_key,
            "opensubtitles_user_agent": req.user_agent,
        }

    # Fallback to saved DB values if fields are empty
    stmt = select(Setting)
    res_db = await db.execute(stmt)
    records = {r.key: r.value for r in res_db.scalars().all()}
    file_cfg = read_config_file()
    env_cfg = get_env_overrides()
    for k, v in {**file_cfg, **env_cfg}.items():
        if not records.get(k) and v is not None and str(v).strip():
            records[k] = json.dumps(v) if isinstance(v, (list, dict)) else str(v)

    if svc == "ollama":
        url = cfg.get("ollama_url") or cfg.get("url") or records.get("ollama_url", "http://localhost:11434")
        res = await OllamaClient.test_connection(url)
        return ConnectionTestResponse(
            service="ollama",
            success=res.get("success", False),
            message=res.get("message", ""),
            available_models=res.get("available_models", []),
            details=res.get("details")
        )

    elif svc == "sonarr":
        url = cfg.get("sonarr_url") or cfg.get("url") or records.get("sonarr_url", "")
        key = cfg.get("sonarr_api_key") or cfg.get("api_key") or records.get("sonarr_api_key", "")
        res = await SonarrClient.test_connection(url, key)
        return ConnectionTestResponse(
            service="sonarr",
            success=res.get("success", False),
            message=res.get("message", ""),
            details=res.get("details")
        )

    elif svc == "tmdb":
        key = cfg.get("tmdb_api_key") or cfg.get("api_key") or records.get("tmdb_api_key", "")
        res = await TMDBClient.test_connection(key)
        return ConnectionTestResponse(
            service="tmdb",
            success=res.get("success", False),
            message=res.get("message", "")
        )

    elif svc == "tvmaze":
        res = await TVmazeClient.test_connection()
        return ConnectionTestResponse(
            service="tvmaze",
            success=res.get("success", False),
            message=res.get("message", "")
        )

    elif svc == "omdb":
        key = cfg.get("omdb_api_key") or cfg.get("api_key") or records.get("omdb_api_key", "")
        res = await OMDbClient.test_connection(key)
        return ConnectionTestResponse(
            service="omdb",
            success=res.get("success", False),
            message=res.get("message", "")
        )

    elif svc == "subdl":
        key = cfg.get("subdl_api_key") or cfg.get("api_key") or records.get("subdl_api_key", "")
        res = await SubDLClient.test_connection(key)
        return ConnectionTestResponse(
            service="subdl",
            success=res.get("success", False),
            message=res.get("message", "")
        )

    elif svc == "opensubtitles":
        key = cfg.get("opensubtitles_api_key") or cfg.get("api_key") or records.get("opensubtitles_api_key", "")
        ua = cfg.get("opensubtitles_user_agent") or cfg.get("user_agent") or records.get("opensubtitles_user_agent", "DBarr v0.1")
        res = await OpenSubtitlesClient.test_connection(key, ua)
        return ConnectionTestResponse(
            service="opensubtitles",
            success=res.get("success", False),
            message=res.get("message", "")
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown service: {svc}")
