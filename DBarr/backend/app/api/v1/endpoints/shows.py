import asyncio
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from backend.app.core.database import get_db, AsyncSessionLocal
from backend.app.models.show import Show
from backend.app.models.episode import Episode
from backend.app.models.job import Job
from backend.app.models.setting import Setting
from backend.app.schemas.show import (
    ShowResponse,
    ShowBriefResponse,
    SonarrShowLookup,
    ShowImportRequest,
    BatchImportRequest,
)
from backend.app.services.sonarr_client import SonarrClient
from backend.app.services.concurrency_manager import concurrency_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/shows", tags=["shows"])


@router.get("", response_model=List[ShowBriefResponse])
async def list_shows(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Show)
        .options(selectinload(Show.episodes))
        .order_by(Show.title)
    )
    res = await db.execute(stmt)
    shows = res.scalars().all()

    result = []
    for s in shows:
        ep_count = len(s.episodes)
        verified_count = sum(1 for e in s.episodes if e.ai_verification_status in ["EXACT_MATCH", "AI_MATCHED"])
        result.append(
            ShowBriefResponse(
                id=s.id,
                sonarr_series_id=s.sonarr_series_id,
                title=s.title,
                year=s.year,
                status=s.status,
                poster_url=s.poster_url,
                original_language=s.original_language or "English",
                audit_status=s.audit_status or "NOT_AUDITED",
                monitored=s.monitored,
                tvdb_id=s.tvdb_id,
                tmdb_id=s.tmdb_id,
                imdb_id=s.imdb_id,
                tvmaze_id=s.tvmaze_id,
                episode_count=ep_count,
                verified_episode_count=verified_count,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return result


@router.get("/{show_id}", response_model=ShowResponse)
async def get_show(show_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Show)
        .where(Show.id == show_id)
        .options(
            selectinload(Show.episodes).selectinload(Episode.transcripts),
            selectinload(Show.episodes).selectinload(Episode.source_variations),
        )
    )
    res = await db.execute(stmt)
    show = res.scalars().first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    # Sort episodes strictly: Season 1..N, then Specials (0)
    def ep_sort(e: Episode):
        s = 999999 if e.season_number == 0 else e.season_number
        return (s, e.episode_number)

    show.episodes.sort(key=ep_sort)
    return show


@router.delete("/{show_id}")
async def delete_show(show_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Show).where(Show.id == show_id)
    res = await db.execute(stmt)
    show = res.scalars().first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    await db.delete(show)
    await db.commit()
    return {"success": True, "message": f"Show '{show.title}' deleted successfully"}


@router.get("/lookup/sonarr", response_model=List[SonarrShowLookup])
async def lookup_sonarr_shows(db: AsyncSession = Depends(get_db)):
    # Retrieve Sonarr credentials
    stmt = select(Setting)
    res = await db.execute(stmt)
    records = {r.key: r.value for r in res.scalars().all()}
    sonarr_url = records.get("sonarr_url", "http://localhost:8989")
    sonarr_api_key = records.get("sonarr_api_key", "")

    if not sonarr_api_key:
        raise HTTPException(status_code=400, detail="Sonarr API key is not configured in Settings.")

    try:
        sonarr_shows = await SonarrClient.get_series(sonarr_url, sonarr_api_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch series from Sonarr: {str(e)}")

    # Check which shows are already in DBarr
    existing_stmt = select(Show.sonarr_series_id)
    existing_res = await db.execute(existing_stmt)
    existing_ids = set(existing_res.scalars().all())

    results = []
    for s in sonarr_shows:
        results.append(
            SonarrShowLookup(
                sonarr_series_id=s["sonarr_series_id"],
                title=s["title"],
                sort_title=s.get("sort_title"),
                year=s.get("year"),
                status=s.get("status"),
                overview=s.get("overview"),
                poster_url=s.get("poster_url"),
                original_language=s.get("original_language", "English"),
                season_count=s.get("season_count", 0),
                episode_count=s.get("episode_count", 0),
                monitored=s.get("monitored", True),
                tvdb_id=s.get("tvdb_id"),
                tmdb_id=s.get("tmdb_id"),
                imdb_id=s.get("imdb_id"),
                path=s.get("path"),
                already_imported=(s["sonarr_series_id"] in existing_ids),
            )
        )
    return results


async def run_import_pipeline(sonarr_series_id: int, job_id: int, scan_mode: str = "full"):
    async with concurrency_manager.job_semaphore:
        concurrency_manager.clear_cancellation(job_id)
        current_task = asyncio.current_task()
        if current_task:
            concurrency_manager.register_task(job_id, current_task)

        try:
            await concurrency_manager.append_log(job_id, f"Starting ingestion pipeline for Sonarr Series ID {sonarr_series_id}", 5.0)

            async with AsyncSessionLocal() as db:
                # Load settings
                stmt_set = select(Setting)
                res_set = await db.execute(stmt_set)
                settings_map = {r.key: r.value for r in res_set.scalars().all()}
                sonarr_url = settings_map.get("sonarr_url", "http://localhost:8989")
                sonarr_api_key = settings_map.get("sonarr_api_key", "")

                if not sonarr_api_key:
                    raise ValueError("Sonarr API key is missing. Please configure it in Settings.")

                # Fetch series details
                await concurrency_manager.append_log(job_id, "Connecting to Sonarr to fetch series metadata...", 10.0)
                series_data = await SonarrClient.get_series_detail(sonarr_url, sonarr_api_key, sonarr_series_id)

                # Extract poster
                poster_url = None
                for img in series_data.get("images", []):
                    if img.get("coverType") == "poster":
                        remote_url = img.get("remoteUrl")
                        url_path = img.get("url")
                        clean_url = sonarr_url.rstrip("/")
                        poster_url = remote_url or (f"{clean_url}{url_path}" if url_path else None)
                        break

                # Extract native language
                orig_lang = "English"
                lang_obj = series_data.get("originalLanguage")
                if isinstance(lang_obj, dict):
                    orig_lang = lang_obj.get("name", "English")
                elif isinstance(lang_obj, str) and lang_obj:
                    orig_lang = lang_obj

                # Create or update Show record
                res_show = await db.execute(select(Show).where(Show.sonarr_series_id == sonarr_series_id))
                show = res_show.scalars().first()
                if not show:
                    show = Show(
                        sonarr_series_id=sonarr_series_id,
                        title=series_data.get("title", f"Series {sonarr_series_id}"),
                        clean_title=series_data.get("cleanTitle"),
                        sort_title=series_data.get("sortTitle"),
                        year=series_data.get("year"),
                        status=series_data.get("status"),
                        overview=series_data.get("overview"),
                        poster_url=poster_url,
                        original_language=orig_lang,
                        tvdb_id=series_data.get("tvdbId"),
                        tmdb_id=series_data.get("tmdbId"),
                        imdb_id=series_data.get("imdbId"),
                        path=series_data.get("path"),
                        monitored=series_data.get("monitored", True),
                    )
                    db.add(show)
                    await db.flush()
                else:
                    show.title = series_data.get("title", show.title)
                    show.year = series_data.get("year", show.year)
                    show.overview = series_data.get("overview", show.overview)
                    show.poster_url = poster_url or show.poster_url
                    show.original_language = orig_lang or show.original_language
                    show.tvdb_id = series_data.get("tvdbId", show.tvdb_id)
                    show.tmdb_id = series_data.get("tmdbId", show.tmdb_id)
                    show.imdb_id = series_data.get("imdbId", show.imdb_id)
                    show.monitored = series_data.get("monitored", show.monitored)

                # Link job to show
                res_j = await db.execute(select(Job).where(Job.id == job_id))
                db_job = res_j.scalars().first()
                if db_job:
                    db_job.show_id = show.id
                    db_job.status = "RUNNING"
                await db.commit()

                await concurrency_manager.append_log(
                    job_id,
                    f"Show record saved: '{show.title}' (Native Language: {show.original_language})",
                    25.0
                )

                # Fetch episodes
                await concurrency_manager.append_log(job_id, "Fetching episode roster from Sonarr...", 35.0)
                raw_episodes = await SonarrClient.get_episodes(sonarr_url, sonarr_api_key, sonarr_series_id)

                # Sort episodes strictly: Season 1..N ascending, followed by Specials (Season 0)
                def sort_key(e: Dict[str, Any]):
                    s_num = e.get("seasonNumber", 1)
                    ep_num = e.get("episodeNumber", 1)
                    season_order = 999999 if s_num == 0 else s_num
                    return (season_order, ep_num)

                sorted_episodes = sorted(raw_episodes, key=sort_key)

                await concurrency_manager.append_log(
                    job_id,
                    f"Processing {len(sorted_episodes)} episodes in strict order (Season 1 → N → Specials)...",
                    45.0
                )

                # Ingest episodes
                total_eps = len(sorted_episodes)
                for idx, ep_data in enumerate(sorted_episodes, start=1):
                    if concurrency_manager.is_cancelled(job_id):
                        await concurrency_manager.append_log(job_id, "Job cancelled by user request.")
                        return

                    sonarr_ep_id = ep_data.get("id")
                    s_num = ep_data.get("seasonNumber", 1)
                    e_num = ep_data.get("episodeNumber", 1)
                    title = ep_data.get("title", f"Episode {e_num}")

                    res_ep = await db.execute(
                        select(Episode).where(Episode.sonarr_episode_id == sonarr_ep_id)
                    )
                    ep = res_ep.scalars().first()
                    if not ep:
                        ep = Episode(
                            show_id=show.id,
                            sonarr_episode_id=sonarr_ep_id,
                            season_number=s_num,
                            episode_number=e_num,
                            absolute_episode_number=ep_data.get("absoluteEpisodeNumber"),
                            title=title,
                            overview=ep_data.get("overview"),
                            air_date=ep_data.get("airDate"),
                            has_file=ep_data.get("hasFile", False),
                            monitored=ep_data.get("monitored", True),
                        )
                        db.add(ep)
                    else:
                        ep.title = title
                        ep.overview = ep_data.get("overview", ep.overview)
                        ep.air_date = ep_data.get("airDate", ep.air_date)
                        ep.has_file = ep_data.get("hasFile", ep.has_file)
                        ep.monitored = ep_data.get("monitored", ep.monitored)

                    # Update progress every 10 episodes or at completion
                    if idx % 10 == 0 or idx == total_eps:
                        pct = 45.0 + (float(idx) / float(total_eps) * 50.0)
                        await concurrency_manager.append_log(
                            job_id,
                            f"Ingested {idx}/{total_eps} episodes (Current: S{s_num:02d}E{e_num:02d} - {title})",
                            pct
                        )

                await db.commit()

                # Mark completed
                await concurrency_manager.append_log(job_id, f"Successfully imported '{show.title}' with {total_eps} episodes.", 100.0)
                res_j2 = await db.execute(select(Job).where(Job.id == job_id))
                db_job2 = res_j2.scalars().first()
                if db_job2:
                    db_job2.status = "COMPLETED"
                    db_job2.finished_at = datetime.utcnow()
                await db.commit()

        except asyncio.CancelledError:
            await concurrency_manager.append_log(job_id, "Job execution cancelled.")
            async with AsyncSessionLocal() as db:
                res_j = await db.execute(select(Job).where(Job.id == job_id))
                j = res_j.scalars().first()
                if j:
                    j.status = "CANCELLED"
                    j.finished_at = datetime.utcnow()
                await db.commit()
        except Exception as e:
            logger.exception(f"Error in import pipeline job {job_id}")
            await concurrency_manager.append_log(job_id, f"Error: {str(e)}")
            async with AsyncSessionLocal() as db:
                res_j = await db.execute(select(Job).where(Job.id == job_id))
                j = res_j.scalars().first()
                if j:
                    j.status = "FAILED"
                    j.finished_at = datetime.utcnow()
                await db.commit()
        finally:
            concurrency_manager.unregister_task(job_id)


@router.post("/import")
async def import_show(
    payload: ShowImportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # Create Job record
    job = Job(
        job_type="IMPORT_SHOW",
        status="PENDING",
        progress=0.0,
        message=f"Queued import for Sonarr series ID {payload.sonarr_series_id}",
        payload=json.dumps({"sonarr_series_id": payload.sonarr_series_id, "scan_mode": payload.scan_mode}),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Launch task in background
    background_tasks.add_task(
        run_import_pipeline,
        sonarr_series_id=payload.sonarr_series_id,
        job_id=job.id,
        scan_mode=payload.scan_mode
    )

    return {"success": True, "job_id": job.id, "message": "Import job queued successfully"}


@router.post("/import-batch")
async def import_shows_batch(
    payload: BatchImportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    if not payload.series_ids:
        raise HTTPException(status_code=400, detail="No series IDs provided for batch import.")

    job_ids = []
    for s_id in payload.series_ids:
        job = Job(
            job_type="BATCH_IMPORT",
            status="PENDING",
            progress=0.0,
            message=f"Queued batch import for Sonarr series ID {s_id}",
            payload=json.dumps({"sonarr_series_id": s_id, "scan_mode": payload.scan_mode}),
        )
        db.add(job)
        await db.flush()
        job_ids.append(job.id)

        # Queue each series
        background_tasks.add_task(
            run_import_pipeline,
            sonarr_series_id=s_id,
            job_id=job.id,
            scan_mode=payload.scan_mode
        )

    await db.commit()
    return {
        "success": True,
        "job_ids": job_ids,
        "count": len(job_ids),
        "message": f"Queued batch import for {len(job_ids)} shows successfully"
    }
