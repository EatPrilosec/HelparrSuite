import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.core.database import AsyncSessionLocal
from backend.app.models.show import Show
from backend.app.models.episode import Episode
from backend.app.models.transcript import Transcript
from backend.app.models.source_metadata import EpisodeSourceMetadata
from backend.app.models.job import Job
from backend.app.models.setting import Setting
from backend.app.core.config_manager import read_config_file, get_env_overrides
from backend.app.services.concurrency_manager import concurrency_manager
from backend.app.services.ollama_client import OllamaClient
from backend.app.services.opensubtitles_client import OpenSubtitlesClient
from backend.app.services.subdl_client import SubDLClient
from backend.app.services.transcript_service import TranscriptService
from backend.app.services.tmdb_client import TMDBClient
from backend.app.services.tvmaze_client import TVmazeClient
from backend.app.services.omdb_client import OMDbClient

logger = logging.getLogger(__name__)

LANGUAGE_CODE_MAP = {
    "english": "en",
    "japanese": "ja",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "korean": "ko",
    "italian": "it",
    "chinese": "zh",
    "portuguese": "pt",
    "russian": "ru",
    "dutch": "nl",
    "swedish": "sv",
    "norwegian": "no",
    "danish": "da",
    "finnish": "fi",
    "polish": "pl",
}


def resolve_language_code(lang: Optional[str]) -> str:
    if not lang:
        return "en"
    clean = lang.strip().lower()
    if len(clean) == 2:
        return clean
    return LANGUAGE_CODE_MAP.get(clean, "en")


def clean_html_summary(html: Optional[str]) -> str:
    if not html:
        return ""
    return re.sub(r"<[^>]+>", "", html).strip()


class VerificationEngine:
    @staticmethod
    async def get_effective_settings(db: AsyncSession) -> Dict[str, Any]:
        stmt = select(Setting)
        res = await db.execute(stmt)
        records = {r.key: r.value for r in res.scalars().all()}
        file_cfg = read_config_file()
        env_cfg = get_env_overrides()
        for k, v in {**file_cfg, **env_cfg}.items():
            if not records.get(k) and v is not None and str(v).strip():
                records[k] = json.dumps(v) if isinstance(v, (list, dict)) else str(v)
        return records

    @staticmethod
    async def run_show_verification(show_id: int, job_id: int):
        async with concurrency_manager.job_semaphore:
            concurrency_manager.clear_cancellation(job_id)
            current_task = asyncio.current_task()
            if current_task:
                concurrency_manager.register_task(job_id, current_task)
            try:
                await VerificationEngine.execute_show_verification_steps(show_id, job_id)
            except asyncio.CancelledError:
                await concurrency_manager.append_log(job_id, "Job execution cancelled by user request.")
                async with AsyncSessionLocal() as db:
                    res_j = await db.execute(select(Job).where(Job.id == job_id))
                    j = res_j.scalars().first()
                    if j:
                        j.status = "CANCELLED"
                        j.finished_at = datetime.utcnow()
                    await db.commit()
            except Exception as e:
                logger.exception(f"Error in verification engine job {job_id}")
                await concurrency_manager.append_log(job_id, f"Verification Error: {str(e)}")
                async with AsyncSessionLocal() as db:
                    res_j = await db.execute(select(Job).where(Job.id == job_id))
                    j = res_j.scalars().first()
                    if j:
                        j.status = "FAILED"
                        j.finished_at = datetime.utcnow()
                        j.message = f"Verification error: {str(e)}"
                    await db.commit()
            finally:
                concurrency_manager.unregister_task(job_id)

    @staticmethod
    async def execute_show_verification_steps(show_id: int, job_id: int):
        await concurrency_manager.append_log(job_id, f"Initializing AI Verification Engine for Show ID {show_id}...", 2.0)

        async with AsyncSessionLocal() as db:
            cfg = await VerificationEngine.get_effective_settings(db)
                    
            # Ollama config
            ollama_url = cfg.get("ollama_url", "http://192.168.8.56:11434")
            if "localhost" in ollama_url or "127.0.0.1" in ollama_url:
                ollama_url = "http://192.168.8.56:11434"
            ollama_primary = cfg.get("ollama_primary_model", "gemma4:e2b")
            fallbacks_raw = cfg.get("ollama_fallback_models")
            ollama_fallbacks: List[str] = []
            if fallbacks_raw:
                try:
                    parsed = json.loads(fallbacks_raw) if isinstance(fallbacks_raw, str) else fallbacks_raw
                    if isinstance(parsed, list):
                        ollama_fallbacks = [str(m).strip() for m in parsed if str(m).strip()]
                except Exception:
                    if isinstance(fallbacks_raw, str):
                        ollama_fallbacks = [m.strip() for m in fallbacks_raw.split(",") if m.strip()]
            if not ollama_fallbacks:
                ollama_fallbacks = ["dzgg/Gemma-4-E2B-it-uncensored-GGUF:Q4_K_M", "gemma4-obliterated:latest"]

            # Provider keys
            opensubs_key = cfg.get("opensubtitles_api_key", "")
            opensubs_ua = cfg.get("opensubtitles_user_agent", "DBarr v0.1")
            opensubs_user = cfg.get("opensubtitles_username", "")
            opensubs_pass = cfg.get("opensubtitles_password", "")
            opensubs_token = None
            if opensubs_user and opensubs_pass and opensubs_key:
                try:
                    opensubs_token = await OpenSubtitlesClient.get_token(opensubs_key, opensubs_ua, opensubs_user, opensubs_pass)
                except Exception as e:
                    logger.warning(f"OpenSubtitles login token fetch failed: {e}")
            subdl_key = cfg.get("subdl_api_key", "")
            tmdb_key = cfg.get("tmdb_api_key", "")
            omdb_key = cfg.get("omdb_api_key", "")

            # Load Show
            res_show = await db.execute(
                select(Show)
                .where(Show.id == show_id)
                .options(
                    selectinload(Show.episodes).selectinload(Episode.transcripts),
                    selectinload(Show.episodes).selectinload(Episode.source_variations),
                )
            )
            show = res_show.scalars().first()
            if not show:
                raise ValueError(f"Show ID {show_id} not found")

            # Update Job record to RUNNING
            res_j = await db.execute(select(Job).where(Job.id == job_id))
            db_job = res_j.scalars().first()
            if db_job:
                db_job.show_id = show.id
                db_job.status = "RUNNING"
                db_job.message = f"Verifying '{show.title}' with Ollama ({ollama_primary})"
            await db.commit()

            lang_code = resolve_language_code(show.original_language)
            await concurrency_manager.append_log(
                job_id,
                f"Show: '{show.title}' (Native Language: {show.original_language} -> '{lang_code}'). Total episodes: {len(show.episodes)}",
                5.0
            )

            # External metadata caches per season / show
            tmdb_season_cache: Dict[int, List[Dict[str, Any]]] = {}
            omdb_season_cache: Dict[int, List[Dict[str, Any]]] = {}
            tvmaze_episodes_cache: Optional[List[Dict[str, Any]]] = None

            # If TVmaze ID not set on show, attempt lookup
            if not show.tvmaze_id:
                try:
                    tvmaze_show = await TVmazeClient.lookup_show(
                        tvdb_id=show.tvdb_id,
                        imdb_id=show.imdb_id,
                        title=show.title
                    )
                    if tvmaze_show and "id" in tvmaze_show:
                        show.tvmaze_id = tvmaze_show["id"]
                        await db.commit()
                        await concurrency_manager.append_log(job_id, f"Discovered TVmaze Show ID: {show.tvmaze_id}")
                except Exception as e:
                    logger.warning(f"TVmaze lookup error for {show.title}: {e}")

            # If TMDB ID not set, attempt lookup via external TVDB ID or title
            if not show.tmdb_id and tmdb_key:
                try:
                    if show.tvdb_id:
                        tmdb_id = await TMDBClient.find_by_external_id(tmdb_key, str(show.tvdb_id), "tvdb_id")
                        if tmdb_id:
                            show.tmdb_id = tmdb_id
                            await db.commit()
                    if not show.tmdb_id and show.imdb_id:
                        tmdb_id = await TMDBClient.find_by_external_id(tmdb_key, show.imdb_id, "imdb_id")
                        if tmdb_id:
                            show.tmdb_id = tmdb_id
                            await db.commit()
                except Exception as e:
                    logger.warning(f"TMDB lookup error for {show.title}: {e}")

            max_concurrent_ai = int(cfg.get("max_concurrent_ollama_requests", 1)) if str(cfg.get("max_concurrent_ollama_requests", "")).isdigit() else 1
            max_concurrent_episodes = max(1, max_concurrent_ai)

            # Pre-fetch TVmaze episode roster if show ID is available
            if show.tvmaze_id:
                try:
                    tvmaze_episodes_cache = await TVmazeClient.get_episodes(show.tvmaze_id)
                except Exception as e:
                    logger.warning(f"Failed to fetch TVmaze episodes: {e}")

            # Sort episodes strictly: Season 1..N ascending, then Specials (Season 0)
            def ep_sort(e: Episode):
                s = 999999 if e.season_number == 0 else e.season_number
                return (s, e.episode_number)

            sorted_episodes = sorted(show.episodes, key=ep_sort)
            total_eps = len(sorted_episodes)

            # Track already-claimed external IDs to ensure strict 1-to-1 uniqueness across episodes
            claimed_tmdb_ids = set()
            claimed_tvm_ids = set()
            claimed_omdb_ids = set()
            for ep_existing in show.episodes:
                for v in ep_existing.source_variations:
                    if v.source_name == "tmdb" and v.source_episode_id:
                        claimed_tmdb_ids.add(str(v.source_episode_id))
                    elif v.source_name == "tvmaze" and v.source_episode_id:
                        claimed_tvm_ids.add(str(v.source_episode_id))
                    elif v.source_name == "omdb" and v.source_episode_id:
                        claimed_omdb_ids.add(str(v.source_episode_id))

            show_title = show.title
            show_imdb_id = show.imdb_id
            show_tmdb_id = show.tmdb_id
            show_tvmaze_id = show.tvmaze_id

            state_lock = asyncio.Lock()
            progress_lock = asyncio.Lock()
            completed_count = 0

            async def process_episode(idx: int, ep_id: int):
                nonlocal completed_count
                if concurrency_manager.is_cancelled(job_id):
                    return

                async with AsyncSessionLocal() as ep_db:
                    res_ep = await ep_db.execute(
                        select(Episode)
                        .where(Episode.id == ep_id)
                        .options(
                            selectinload(Episode.transcripts),
                            selectinload(Episode.source_variations),
                        )
                    )
                    ep = res_ep.scalars().first()
                    if not ep:
                        return

                    s_num = ep.season_number
                    e_num = ep.episode_number
                    ep_label = f"S{s_num:02d}E{e_num:02d}"

                    # Skip if already fully verified with both primary metadata providers
                    has_tmdb = any(v.source_name == "tmdb" for v in ep.source_variations)
                    has_tvm = any(v.source_name == "tvmaze" for v in ep.source_variations)
                    if ep.ai_verification_status == "AI_MATCHED" and (has_tmdb and has_tvm):
                        async with progress_lock:
                            completed_count += 1
                            pct = 5.0 + (float(completed_count) / float(total_eps) * 92.0)
                            await concurrency_manager.append_log(
                                job_id,
                                f"[{completed_count}/{total_eps}] {ep_label} is already verified (AI_MATCHED). Skipping.",
                                pct
                            )
                        return

                    await concurrency_manager.append_log(
                        job_id,
                        f"[{idx}/{total_eps}] Auditing {ep_label} - \"{ep.title}\"..."
                    )

                    audit_trail: List[str] = []

                    # =========================================================================
                    # STEP 1: Native Subtitle & Canonical Transcript Discovery (LLM Pass 1)
                    # =========================================================================
                    transcript_record = next((t for t in ep.transcripts if t.is_native_language), None)
                    transcript_text = transcript_record.raw_content if transcript_record else ""
                    transcript_preview = transcript_record.preview_text if transcript_record else ""

                    if not transcript_record:
                        candidate_subs: List[Dict[str, Any]] = []
                        provider_used = "opensubtitles"
                        raw_sub_text = None
                        provider_error = None

                        if opensubs_key:
                            try:
                                candidate_subs = await OpenSubtitlesClient.search_subtitles(
                                    api_key=opensubs_key,
                                    user_agent=opensubs_ua,
                                    parent_imdb_id=show_imdb_id,
                                    parent_tmdb_id=show_tmdb_id,
                                    query=show_title,
                                    season_number=s_num,
                                    episode_number=e_num,
                                    languages=lang_code,
                                    token=opensubs_token
                                )
                                if candidate_subs:
                                    first_sub = candidate_subs[0]
                                    files = first_sub.get("attributes", {}).get("files", [])
                                    file_id = files[0].get("file_id") if files else None
                                    if file_id:
                                        raw_sub_text, os_err = await OpenSubtitlesClient.download_subtitle_file(
                                            api_key=opensubs_key,
                                            file_id=file_id,
                                            user_agent=opensubs_ua,
                                            token=opensubs_token
                                        )
                                        if os_err:
                                            provider_error = os_err
                            except Exception as e:
                                logger.warning(f"OpenSubtitles search/download failed for {ep_label}: {e}")
                                provider_error = f"OpenSubtitles error: {str(e)}"

                        if not raw_sub_text and subdl_key:
                            try:
                                subdl_subs = await SubDLClient.search_subtitles(
                                    api_key=subdl_key,
                                    imdb_id=show_imdb_id,
                                    tmdb_id=show_tmdb_id,
                                    film_name=show_title,
                                    season_number=s_num,
                                    episode_number=e_num,
                                    languages=lang_code
                                )
                                if subdl_subs:
                                    first_sub = subdl_subs[0]
                                    sub_url = first_sub.get("url") or first_sub.get("download_link")
                                    if sub_url:
                                        raw_sub_text, subdl_err = await SubDLClient.download_subtitle_content(sub_url)
                                        if raw_sub_text:
                                            provider_used = "subdl"
                                        elif subdl_err:
                                            provider_error = subdl_err
                            except Exception as e:
                                logger.warning(f"SubDL fallback failed for {ep_label}: {e}")
                                if not provider_error:
                                    provider_error = f"SubDL error: {str(e)}"

                        if raw_sub_text:
                            clean_text, preview = TranscriptService.clean_subtitle_text(raw_sub_text)
                            if clean_text:
                                async with concurrency_manager.ollama_semaphore:
                                    pass1_prompt = f"""Target Episode:
- Series: "{show_title}"
- Season: {s_num}, Episode: {e_num}
- Title: "{ep.title}"
- Plot Overview: "{ep.overview or 'N/A'}"
- Air Date: {ep.air_date or 'N/A'}

Candidate Subtitle Dialogue (Preview):
"{preview[:600]}"

Inspect whether this subtitle transcript belongs to the target episode based on the title, dialogue, and plot.
Also extract 2-4 opening or key dialogue lines as dialogue anchors for audio matching.

Respond with JSON schema:
{{
  "matched": true,
  "confidence": 1.0,
  "reasoning": "Explanation of dialogue match",
  "dialogue_anchors": ["line 1", "line 2"]
}}"""
                                    try:
                                        llm_p1 = await OllamaClient.query_with_fallback_json(
                                            base_url=ollama_url,
                                            primary_model=ollama_primary,
                                            fallback_models=ollama_fallbacks,
                                            user_prompt=pass1_prompt,
                                            system_prompt="You are DBarr's authoritative subtitle & dialogue auditor. 100% accuracy required. Never guess.",
                                            timeout=120.0,
                                            options={"temperature": 0.1, "num_predict": 256}
                                        )
                                        p1_data = llm_p1.get("data", {})
                                        if p1_data.get("matched") and float(p1_data.get("confidence", 0)) >= 0.75:
                                            anchors = p1_data.get("dialogue_anchors", [])
                                            new_transcript = Transcript(
                                                episode_id=ep.id,
                                                language=lang_code,
                                                is_native_language=True,
                                                source_provider=provider_used,
                                                raw_content=clean_text,
                                                preview_text=preview,
                                                dialogue_anchors=json.dumps(anchors) if isinstance(anchors, list) else str(anchors),
                                            )
                                            ep_db.add(new_transcript)
                                            transcript_text = clean_text
                                            transcript_preview = preview
                                            audit_trail.append(f"Transcript verified via {provider_used} ({p1_data.get('confidence', 1.0):.2f}): {p1_data.get('reasoning', '')}")
                                            await concurrency_manager.append_log(job_id, f"  -> [Pass 1] {ep_label} subtitle transcript locked via {provider_used}")
                                    except Exception as e:
                                        logger.warning(f"LLM Pass 1 failed for {ep_label}: {e}")

                        if not transcript_preview:
                            transcript_preview = f"{ep.title}. {ep.overview or ''}"
                            reason = provider_error or "transcript missing on internet providers"
                            audit_trail.append(f"Internet transcript unavailable ({reason}); baseline plot used")
                            await concurrency_manager.append_log(
                                job_id,
                                f"  -> [Pass 1] Internet subtitle transcript unavailable for {ep_label} ({reason}); using Sonarr baseline plot"
                            )

                    if concurrency_manager.is_cancelled(job_id):
                        return

                    # =========================================================================
                    # STEP 2: TMDB Cumulative Verification (LLM Pass 2)
                    # =========================================================================
                    tmdb_variation = next((v for v in ep.source_variations if v.source_name == "tmdb"), None)
                    if not tmdb_variation and tmdb_key and show_tmdb_id:
                        async with state_lock:
                            if s_num not in tmdb_season_cache:
                                try:
                                    tmdb_season_cache[s_num] = await TMDBClient.get_season_episodes(tmdb_key, show_tmdb_id, s_num)
                                except Exception as e:
                                    logger.warning(f"Failed to fetch TMDB season {s_num}: {e}")
                                    tmdb_season_cache[s_num] = []
                            candidates = tmdb_season_cache.get(s_num, [])
                            avail_candidates = [c for c in candidates if str(c.get("id")) not in claimed_tmdb_ids]
                            target_candidates = avail_candidates if avail_candidates else candidates

                        if target_candidates:
                            cand_summaries = []
                            for c in target_candidates:
                                cand_summaries.append({
                                    "tmdb_episode_id": c.get("id"),
                                    "season_number": c.get("season_number"),
                                    "episode_number": c.get("episode_number"),
                                    "name": c.get("name"),
                                    "overview": c.get("overview", "")[:200],
                                    "air_date": c.get("air_date")
                                })

                            async with concurrency_manager.ollama_semaphore:
                                pass2_prompt = f"""Target Episode Baseline (Sonarr):
- Season: {s_num}, Episode: {e_num}
- Title: "{ep.title}"
- Overview: "{ep.overview or 'N/A'}"
- Air Date: {ep.air_date or 'N/A'}
- Verified Native Dialogue Transcript Excerpt: "{transcript_preview[:300]}"

Candidate Episodes from TMDB (Season {s_num}):
{json.dumps(cand_summaries[:20], indent=2)}

Match Priority Instructions:
1. TITLE & SEMANTIC VARIATIONS (Highest Priority): Match based on identical or closely matching titles, alternate titles, or translated titles.
2. NARRATIVE PLOT & STORY CONTENT: Confirm that the premise, characters, and events described in the candidate overview match the baseline episode.
3. AIR DATE & EPISODE NUMBER (Lowest Priority / Tiebreaker Only): Broadcast dates and episode numbers routinely diverge across syndication, streaming, and regional release orders. NEVER match solely on episode number or broadcast date if the title or narrative premise describes a completely different episode.

Identify the exact matching TMDB episode. 
Respond ONLY in JSON format:
{{
  "matched": true,
  "tmdb_episode_id": 12345,
  "confidence": 1.0,
  "reasoning": "Why this TMDB episode matches based on title and narrative",
  "alternate_titles": ["Alt title"]
}}"""
                                try:
                                    llm_p2 = await OllamaClient.query_with_fallback_json(
                                        base_url=ollama_url,
                                        primary_model=ollama_primary,
                                        fallback_models=ollama_fallbacks,
                                        user_prompt=pass2_prompt,
                                        system_prompt="You are DBarr's authoritative episode metadata matcher.",
                                        timeout=120.0,
                                        options={"temperature": 0.1, "num_predict": 256}
                                    )
                                    p2_data = llm_p2.get("data", {})
                                    matched_c_id = p2_data.get("tmdb_episode_id")
                                    matched_c = next((c for c in target_candidates if c.get("id") == matched_c_id), None)
                                    if not matched_c and candidates:
                                        matched_c = next((c for c in candidates if c.get("id") == matched_c_id), None)

                                    if matched_c and p2_data.get("matched", True):
                                        async with state_lock:
                                            claimed_tmdb_ids.add(str(matched_c.get("id")))
                                        tmdb_var = EpisodeSourceMetadata(
                                            episode_id=ep.id,
                                            show_id=show_id,
                                            source_name="tmdb",
                                            source_show_id=str(show_tmdb_id),
                                            source_episode_id=str(matched_c.get("id")),
                                            source_season_number=matched_c.get("season_number"),
                                            source_episode_number=matched_c.get("episode_number"),
                                            title=matched_c.get("name"),
                                            alternate_titles=json.dumps(p2_data.get("alternate_titles", [])),
                                            overview=matched_c.get("overview"),
                                            air_date=matched_c.get("air_date"),
                                            match_method="LLM_TRANSCRIPT_AND_METADATA_CONFIRMED",
                                            match_confidence=float(p2_data.get("confidence", 1.0)),
                                            llm_reasoning=p2_data.get("reasoning", "LLM confirmed TMDB match"),
                                            raw_metadata=json.dumps(matched_c)
                                        )
                                        ep_db.add(tmdb_var)
                                        audit_trail.append(f"TMDB match confirmed (ID: {matched_c.get('id')}, {p2_data.get('confidence', 1.0):.2f})")
                                        await concurrency_manager.append_log(job_id, f"  -> [Pass 2] {ep_label} TMDB mapped: '{matched_c.get('name')}'")
                                except Exception as e:
                                    logger.warning(f"LLM Pass 2 failed for {ep_label}: {e}")

                    if concurrency_manager.is_cancelled(job_id):
                        return

                    # =========================================================================
                    # STEP 3: TVmaze Cumulative Verification (LLM Pass 3)
                    # =========================================================================
                    tvmaze_variation = next((v for v in ep.source_variations if v.source_name == "tvmaze"), None)
                    if not tvmaze_variation and tvmaze_episodes_cache:
                        tvm_candidates = [
                            c for c in tvmaze_episodes_cache
                            if (c.get("season") == s_num) or (s_num == 0 and c.get("season") == 0)
                        ]
                        async with state_lock:
                            avail_tvm = [c for c in tvm_candidates if str(c.get("id")) not in claimed_tvm_ids]
                            target_tvm = avail_tvm if avail_tvm else tvm_candidates

                        if target_tvm:
                            cand_list = []
                            for c in target_tvm:
                                cand_list.append({
                                    "tvmaze_id": c.get("id"),
                                    "season": c.get("season"),
                                    "number": c.get("number"),
                                    "name": c.get("name"),
                                    "overview": clean_html_summary(c.get("summary"))[:200],
                                    "airdate": c.get("airdate")
                                })

                            async with concurrency_manager.ollama_semaphore:
                                pass3_prompt = f"""Target Episode Baseline (Sonarr):
- Season: {s_num}, Episode: {e_num}
- Title: "{ep.title}"
- Overview: "{ep.overview or 'N/A'}"
- Air Date: {ep.air_date or 'N/A'}
- Verified Dialogue Transcript Excerpt: "{transcript_preview[:250]}"

Candidate TVmaze Linear Broadcast Episodes:
{json.dumps(cand_list[:20], indent=2)}

Match Priority Instructions:
1. TITLE & SEMANTIC VARIATIONS (Highest Priority): Match based on identical or closely matching titles, alternate titles, or translated titles.
2. NARRATIVE PLOT & STORY CONTENT: Confirm that the premise, characters, and events described in the candidate overview match the baseline episode.
3. AIR DATE & EPISODE NUMBER (Lowest Priority / Tiebreaker Only): Broadcast dates and episode numbers routinely diverge across regional syndication, streaming releases, production orders, and network re-runs. NEVER match solely on episode number or broadcast date if the title or narrative premise describes a completely different episode.

Select the matching TVmaze broadcast episode.
Respond ONLY in JSON:
{{
  "matched": true,
  "tvmaze_id": 12345,
  "confidence": 1.0,
  "reasoning": "Reason for match based on title and narrative plot"
}}"""
                                try:
                                    llm_p3 = await OllamaClient.query_with_fallback_json(
                                        base_url=ollama_url,
                                        primary_model=ollama_primary,
                                        fallback_models=ollama_fallbacks,
                                        user_prompt=pass3_prompt,
                                        system_prompt="You are DBarr's TVmaze linear broadcast matcher.",
                                        timeout=120.0,
                                        options={"temperature": 0.1, "num_predict": 256}
                                    )
                                    p3_data = llm_p3.get("data", {})
                                    matched_tvm_id = p3_data.get("tvmaze_id")
                                    matched_tvm = next((c for c in target_tvm if c.get("id") == matched_tvm_id), None)
                                    if not matched_tvm and tvm_candidates:
                                        matched_tvm = next((c for c in tvm_candidates if c.get("id") == matched_tvm_id), None)

                                    if matched_tvm and p3_data.get("matched", True):
                                        async with state_lock:
                                            claimed_tvm_ids.add(str(matched_tvm.get("id")))
                                        tvm_var = EpisodeSourceMetadata(
                                            episode_id=ep.id,
                                            show_id=show_id,
                                            source_name="tvmaze",
                                            source_show_id=str(show_tvmaze_id),
                                            source_episode_id=str(matched_tvm.get("id")),
                                            source_season_number=matched_tvm.get("season"),
                                            source_episode_number=matched_tvm.get("number"),
                                            title=matched_tvm.get("name"),
                                            overview=matched_tvm.get("summary"),
                                            air_date=matched_tvm.get("airdate"),
                                            match_method="LLM_LINEAR_BROADCAST_CONFIRMED",
                                            match_confidence=float(p3_data.get("confidence", 1.0)),
                                            llm_reasoning=p3_data.get("reasoning", "TVmaze match confirmed based on title and plot"),
                                            raw_metadata=json.dumps(matched_tvm)
                                        )
                                        ep_db.add(tvm_var)
                                        audit_trail.append(f"TVmaze broadcast match confirmed (ID: {matched_tvm.get('id')})")
                                        await concurrency_manager.append_log(job_id, f"  -> [Pass 3] {ep_label} TVmaze mapped: S{matched_tvm.get('season')}E{matched_tvm.get('number')} '{matched_tvm.get('name')}'")
                                except Exception as e:
                                    logger.warning(f"LLM Pass 3 failed for {ep_label}: {e}")

                    if concurrency_manager.is_cancelled(job_id):
                        return

                    # =========================================================================
                    # STEP 4: OMDb Cumulative Verification (LLM Pass 4)
                    # =========================================================================
                    omdb_variation = next((v for v in ep.source_variations if v.source_name == "omdb"), None)
                    if not omdb_variation and omdb_key and show_imdb_id and s_num > 0:
                        async with state_lock:
                            if s_num not in omdb_season_cache:
                                try:
                                    omdb_season_cache[s_num] = await OMDbClient.get_season_episodes(omdb_key, show_imdb_id, s_num)
                                except Exception as e:
                                    logger.warning(f"Failed to fetch OMDb season {s_num}: {e}")
                                    omdb_season_cache[s_num] = []
                            omdb_candidates = omdb_season_cache.get(s_num, [])
                            avail_omdb = [c for c in omdb_candidates if str(c.get("imdbID")) not in claimed_omdb_ids]
                            target_omdb = avail_omdb if avail_omdb else omdb_candidates

                        if target_omdb:
                            cand_list = []
                            for c in target_omdb:
                                cand_list.append({
                                    "imdb_id": c.get("imdbID"),
                                    "episode": c.get("Episode"),
                                    "title": c.get("Title"),
                                    "released": c.get("Released"),
                                    "imdb_rating": c.get("imdbRating")
                                })

                            async with concurrency_manager.ollama_semaphore:
                                pass4_prompt = f"""Target Episode Baseline (Sonarr):
- Season: {s_num}, Episode: {e_num}
- Title: "{ep.title}"
- Overview: "{ep.overview or 'N/A'}"
- Air Date: {ep.air_date or 'N/A'}
- Verified Dialogue Transcript Excerpt: "{transcript_preview[:250]}"

Candidate OMDb/IMDb Entries (Season {s_num}):
{json.dumps(cand_list[:20], indent=2)}

Match Priority Instructions:
1. TITLE & SEMANTIC VARIATIONS (Highest Priority): Match based on identical or closely matching titles.
2. NARRATIVE PLOT & STORY CONTENT: Confirm that the premise and events match the baseline episode.
3. AIR DATE & EPISODE NUMBER (Lowest Priority / Tiebreaker Only): Broadcast dates and numbering can diverge. NEVER match solely on episode number or date if the title describes a completely different episode.

Confirm the matching IMDb episode entry.
Respond ONLY in JSON:
{{
  "matched": true,
  "imdb_id": "tt1234567",
  "confidence": 1.0,
  "reasoning": "Why this IMDb entry matches based on title"
}}"""
                                try:
                                    llm_p4 = await OllamaClient.query_with_fallback_json(
                                        base_url=ollama_url,
                                        primary_model=ollama_primary,
                                        fallback_models=ollama_fallbacks,
                                        user_prompt=pass4_prompt,
                                        system_prompt="You are DBarr's OMDb/IMDb episode auditor.",
                                        timeout=120.0,
                                        options={"temperature": 0.1, "num_predict": 256}
                                    )
                                    p4_data = llm_p4.get("data", {})
                                    matched_imdb_id = p4_data.get("imdb_id")
                                    matched_omdb = next((c for c in target_omdb if c.get("imdbID") == matched_imdb_id), None)
                                    if not matched_omdb and omdb_candidates:
                                        matched_omdb = next((c for c in omdb_candidates if c.get("imdbID") == matched_imdb_id), None)

                                    if matched_omdb and p4_data.get("matched", True):
                                        async with state_lock:
                                            claimed_omdb_ids.add(str(matched_omdb.get("imdbID")))
                                        omdb_var = EpisodeSourceMetadata(
                                            episode_id=ep.id,
                                            show_id=show_id,
                                            source_name="omdb",
                                            source_show_id=show_imdb_id,
                                            source_episode_id=matched_omdb.get("imdbID"),
                                            source_season_number=s_num,
                                            source_episode_number=int(matched_omdb.get("Episode")) if str(matched_omdb.get("Episode", "")).isdigit() else e_num,
                                            title=matched_omdb.get("Title"),
                                            air_date=matched_omdb.get("Released"),
                                            match_method="LLM_METADATA_CONFIRMED",
                                            match_confidence=float(p4_data.get("confidence", 1.0)),
                                            llm_reasoning=p4_data.get("reasoning", "OMDb match confirmed based on title"),
                                            raw_metadata=json.dumps(matched_omdb)
                                        )
                                        ep_db.add(omdb_var)
                                        audit_trail.append(f"OMDb/IMDb match confirmed ({matched_omdb.get('imdbID')})")
                                        await concurrency_manager.append_log(job_id, f"  -> [Pass 4] {ep_label} OMDb mapped: {matched_omdb.get('imdbID')} '{matched_omdb.get('Title')}'")
                                except Exception as e:
                                    logger.warning(f"LLM Pass 4 failed for {ep_label}: {e}")

                    # =========================================================================
                    # STEP 5: Commit Episode State & Update Audit Status
                    # =========================================================================
                    ep.ai_verification_status = "AI_MATCHED"
                    ep.ai_confidence_score = 1.0
                    ep.ai_audit_notes = " | ".join(audit_trail) if audit_trail else "Roster verified with Sonarr canonical baseline"
                    await ep_db.commit()

                    async with progress_lock:
                        completed_count += 1
                        pct = 5.0 + (float(completed_count) / float(total_eps) * 92.0)
                        await concurrency_manager.append_log(
                            job_id,
                            f"[{completed_count}/{total_eps}] Completed audit for {ep_label} - \"{ep.title}\"",
                            pct
                        )

            # Queue all episodes for worker pool
            queue = asyncio.Queue()
            for idx, ep in enumerate(sorted_episodes, start=1):
                queue.put_nowait((idx, ep.id))

            async def worker():
                while not queue.empty():
                    if concurrency_manager.is_cancelled(job_id):
                        break
                    try:
                        idx, ep_id = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    try:
                        await process_episode(idx, ep_id)
                    except Exception as err:
                        logger.exception(f"Error auditing episode ID {ep_id}: {err}")
                        await concurrency_manager.append_log(job_id, f"Error auditing episode ID {ep_id}: {err}")
                    finally:
                        queue.task_done()

            num_workers = min(max_concurrent_episodes, total_eps) if total_eps > 0 else 1
            await concurrency_manager.append_log(
                job_id,
                f"Starting verification workers for {total_eps} episode(s) (Concurrency: {num_workers} simultaneous episode(s))..."
            )
            worker_tasks = [asyncio.create_task(worker()) for _ in range(num_workers)]
            await asyncio.gather(*worker_tasks)

            # Show completed
            async with AsyncSessionLocal() as final_db:
                res_show_final = await final_db.execute(select(Show).where(Show.id == show_id))
                show_final = res_show_final.scalars().first()
                if show_final:
                    show_final.audit_status = "VERIFIED"
                    show_final.last_audited_at = datetime.utcnow()
                await final_db.commit()

            await concurrency_manager.append_log(
                job_id,
                f"AI Verification Complete! Verified {total_eps} episodes for '{show_title}'.",
                100.0
            )

            async with AsyncSessionLocal() as final_db:
                res_j_end = await final_db.execute(select(Job).where(Job.id == job_id))
                db_job_end = res_j_end.scalars().first()
                if db_job_end:
                    db_job_end.status = "COMPLETED"
                    db_job_end.finished_at = datetime.utcnow()
                    db_job_end.message = f"Successfully verified '{show_title}' ({total_eps} episodes)"
                await final_db.commit()
