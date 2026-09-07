import pytest
from sqlalchemy import select
from backend.app.models.show import Show
from backend.app.models.episode import Episode
from backend.app.models.transcript import Transcript
from backend.app.models.source_metadata import EpisodeSourceMetadata
from backend.app.models.job import Job
from backend.app.models.setting import Setting


@pytest.mark.asyncio
async def test_schema_and_relationships(test_db):
    # 1. Create Show
    show = Show(
        sonarr_series_id=101,
        title="Breaking Bad",
        year=2008,
        original_language="English",
        monitored=True
    )
    test_db.add(show)
    await test_db.flush()
    assert show.id is not None

    # 2. Add Episodes (including Specials Season 0)
    ep0 = Episode(
        show_id=show.id,
        sonarr_episode_id=1000,
        season_number=0,
        episode_number=1,
        title="Special 1"
    )
    ep1 = Episode(
        show_id=show.id,
        sonarr_episode_id=1001,
        season_number=1,
        episode_number=1,
        title="Pilot"
    )
    ep2 = Episode(
        show_id=show.id,
        sonarr_episode_id=1002,
        season_number=1,
        episode_number=2,
        title="Cat's in the Bag..."
    )
    test_db.add_all([ep0, ep1, ep2])
    await test_db.flush()

    # 3. Add Transcript
    transcript = Transcript(
        episode_id=ep1.id,
        language="en",
        is_native_language=True,
        source_provider="opensubtitles",
        raw_content="All right, listen. You and I are going to cook.",
        preview_text="All right, listen...",
        dialogue_anchors='["All right, listen."]'
    )
    test_db.add(transcript)

    # 4. Add Source Variation
    source_meta = EpisodeSourceMetadata(
        episode_id=ep1.id,
        show_id=show.id,
        source_name="tmdb",
        source_season_number=1,
        source_episode_number=1,
        title="Pilot",
        match_method="LLM_METADATA_CONFIRMED",
        match_confidence=1.0,
        llm_reasoning="Exact title and dialogue match confirmed."
    )
    test_db.add(source_meta)
    await test_db.commit()

    # Query and verify
    res = await test_db.execute(select(Show).where(Show.id == show.id))
    fetched_show = res.scalars().first()
    assert fetched_show.title == "Breaking Bad"
    assert fetched_show.original_language == "English"

    res_eps = await test_db.execute(select(Episode).where(Episode.show_id == show.id))
    eps = res_eps.scalars().all()
    assert len(eps) == 3

    # Verify strict ordering: S1..SN, then Specials (0)
    sorted_eps = sorted(eps, key=lambda e: (999999 if e.season_number == 0 else e.season_number, e.episode_number))
    assert sorted_eps[0].title == "Pilot"
    assert sorted_eps[1].title == "Cat's in the Bag..."
    assert sorted_eps[2].title == "Special 1"


@pytest.mark.asyncio
async def test_job_and_setting_models(test_db):
    setting = Setting(key="sonarr_url", value="http://192.168.8.56:8989")
    job = Job(job_type="BATCH_IMPORT", status="PENDING", progress=0.0)
    test_db.add_all([setting, job])
    await test_db.commit()

    res_set = await test_db.execute(select(Setting).where(Setting.key == "sonarr_url"))
    assert res_set.scalars().first().value == "http://192.168.8.56:8989"

    res_j = await test_db.execute(select(Job).where(Job.id == job.id))
    assert res_j.scalars().first().status == "PENDING"
