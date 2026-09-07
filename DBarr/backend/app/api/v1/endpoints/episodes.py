from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.core.database import get_db
from backend.app.models.episode import Episode
from backend.app.schemas.episode import EpisodeResponse

router = APIRouter(prefix="/episodes", tags=["episodes"])


@router.get("/by-show/{show_id}", response_model=List[EpisodeResponse])
async def get_episodes_by_show(
    show_id: int,
    season: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Episode)
        .where(Episode.show_id == show_id)
        .options(
            selectinload(Episode.transcripts),
            selectinload(Episode.source_variations)
        )
    )
    if season is not None:
        stmt = stmt.where(Episode.season_number == season)

    # In DBarr, specials (Season 0) are ordered last:
    # We order by: CASE WHEN season_number = 0 THEN 999999 ELSE season_number END, episode_number
    res = await db.execute(stmt)
    episodes = res.scalars().all()

    # Sort strictly: S1, S2, ..., SN, then S0 (Specials)
    def season_sort_key(ep: Episode):
        s = 999999 if ep.season_number == 0 else ep.season_number
        return (s, ep.episode_number)

    sorted_episodes = sorted(episodes, key=season_sort_key)
    return sorted_episodes


@router.get("/{episode_id}", response_model=EpisodeResponse)
async def get_episode(episode_id: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Episode)
        .where(Episode.id == episode_id)
        .options(
            selectinload(Episode.transcripts),
            selectinload(Episode.source_variations)
        )
    )
    res = await db.execute(stmt)
    episode = res.scalars().first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode
