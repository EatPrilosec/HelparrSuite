import json
import logging
import os
from pathlib import Path
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.models.setting import Setting

logger = logging.getLogger(__name__)

ENV_MAPPINGS = {
    "sonarr_url": ["SONARR_URL", "DBARR_SONARR_URL"],
    "sonarr_api_key": ["SONARR_API_KEY", "DBARR_SONARR_API_KEY"],
    "tmdb_api_key": ["TMDB_API_KEY", "DBARR_TMDB_API_KEY"],
    "tvmaze_api_key": ["TVMAZE_API_KEY", "DBARR_TVMAZE_API_KEY"],
    "omdb_api_key": ["OMDB_API_KEY", "DBARR_OMDB_API_KEY"],
    "subdl_api_key": ["SUBDL_API_KEY", "DBARR_SUBDL_API_KEY"],
    "opensubtitles_api_key": ["OPENSUBTITLES_API_KEY", "DBARR_OPENSUBTITLES_API_KEY"],
    "opensubtitles_user_agent": ["OPENSUBTITLES_USER_AGENT", "DBARR_OPENSUBTITLES_USER_AGENT"],
    "ollama_url": ["OLLAMA_URL", "DBARR_OLLAMA_URL"],
    "ollama_primary_model": ["OLLAMA_PRIMARY_MODEL", "DBARR_OLLAMA_PRIMARY_MODEL"],
}


def get_config_file_path() -> Path:
    return settings.resolved_data_dir / "config.json"


def read_config_file() -> Dict[str, Any]:
    cfg_file = get_config_file_path()
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.error(f"Error reading config file at {cfg_file}: {e}")
    return {}


def write_config_file(data: Dict[str, Any]) -> bool:
    if os.getenv("DBARR_TESTING") == "1":
        return True
    cfg_file = get_config_file_path()
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        # Write to temporary file first then rename for atomic write
        tmp_file = cfg_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp_file.replace(cfg_file)
        return True
    except Exception as e:
        logger.error(f"Error writing config file at {cfg_file}: {e}")
        return False


def get_env_overrides() -> Dict[str, Any]:
    overrides = {}
    for key, env_vars in ENV_MAPPINGS.items():
        for var in env_vars:
            val = os.getenv(var)
            if val is not None and val.strip():
                overrides[key] = val.strip()
                break
    return overrides


async def sync_config_on_startup(db: AsyncSession) -> None:
    """
    On application boot:
    1. Read config.json from /config/config.json (persistent volume).
    2. Check environment variable overrides.
    3. Sync non-empty values into SQLite settings table.
    4. If config.json does not exist yet, create it from SQLite or env vars.
    """
    file_cfg = read_config_file()
    env_cfg = get_env_overrides()

    # Load existing DB records
    stmt = select(Setting)
    res = await db.execute(stmt)
    db_records = {r.key: r.value for r in res.scalars().all()}

    # Merge: DB records < file_cfg < env_cfg
    merged = {**db_records}

    # Update with file config
    for k, v in file_cfg.items():
        if v is not None and (isinstance(v, (int, float, bool, list, dict)) or str(v).strip()):
            val_str = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
            merged[k] = val_str

    # Update with env config
    for k, v in env_cfg.items():
        if v:
            merged[k] = str(v)

    # Upsert into database
    has_db_changes = False
    for k, val_str in merged.items():
        if db_records.get(k) != val_str:
            stmt_item = select(Setting).where(Setting.key == k)
            res_item = await db.execute(stmt_item)
            record = res_item.scalars().first()
            if record:
                record.value = val_str
            else:
                db.add(Setting(key=k, value=val_str))
            has_db_changes = True

    if has_db_changes:
        await db.commit()

    # Always ensure config.json exists on disk with current merged settings
    # Parse back lists/ints for clean human-readable JSON
    clean_json_data = {}
    for k, v in merged.items():
        if isinstance(v, str):
            if (v.startswith("[") and v.endswith("]")) or (v.startswith("{") and v.endswith("}")):
                try:
                    clean_json_data[k] = json.loads(v)
                    continue
                except Exception:
                    pass
            elif v.isdigit() and k in ("max_concurrent_jobs", "max_concurrent_ollama_requests", "ai_batch_size"):
                clean_json_data[k] = int(v)
                continue
        clean_json_data[k] = v

    write_config_file(clean_json_data)
    logger.info(f"Configuration synchronized: {len(clean_json_data)} keys loaded from {get_config_file_path()}")
