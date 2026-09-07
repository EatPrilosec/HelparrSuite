import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.database import get_db


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app"] == "DBarr"
        assert data["port"] == 6781


@pytest.mark.asyncio
async def test_settings_api(test_db):
    app.dependency_overrides[get_db] = lambda: test_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get default settings
        res = await client.get("/api/v1/settings")
        assert res.status_code == 200
        data = res.json()
        assert data["ollama_primary_model"] == "gemma4:e2b"
        assert data["max_concurrent_jobs"] == 1
        assert data["max_concurrent_ollama_requests"] == 1
        assert len(data["ollama_fallback_models"]) >= 1
        assert any("Gemma" in m or "gemma" in m for m in data["ollama_fallback_models"])

        # Update settings
        update_res = await client.post(
            "/api/v1/settings",
            json={
                "ollama_url": "http://localhost:11434",
                "ollama_primary_model": "gemma4:e2b",
                "ollama_fallback_models": ["Gemma-4-E2B-it-uncensored-GGUF:Q4_K_M"],
                "ollama_fallback_model": "Gemma-4-E2B-it-uncensored-GGUF:Q4_K_M",
                "ai_batch_size": 1,
                "sonarr_url": "http://192.168.8.56:8989",
                "sonarr_api_key": "test_key",
                "tmdb_api_key": "",
                "tvmaze_api_key": "",
                "omdb_api_key": "",
                "subdl_api_key": "",
                "opensubtitles_api_key": "",
                "opensubtitles_user_agent": "DBarr v0.1",
                "max_concurrent_jobs": 1,
                "max_concurrent_ollama_requests": 1,
                "default_language": "en"
            }
        )
        assert update_res.status_code == 200

        # Verify updated settings
        res2 = await client.get("/api/v1/settings")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["sonarr_url"] == "http://192.168.8.56:8989"
        assert data2["sonarr_api_key"] == "test_key"

    app.dependency_overrides.clear()


def test_ollama_safety_refusal_detection():
    from backend.app.services.ollama_client import is_safety_refusal
    assert is_safety_refusal("I cannot fulfill this request because it violates safety guidelines.") is True
    assert is_safety_refusal("I am sorry, but I cannot process this episode description.") is True
    assert is_safety_refusal("{\"matched\": true, \"confidence\": 1.0}") is False


def test_transcript_service_cleaning():
    from backend.app.services.transcript_service import TranscriptService
    sample_srt = """1
00:00:01,000 --> 00:00:04,000
[Dramatic music playing]

2
00:00:05,100 --> 00:00:08,200
<i>Mayday, mayday!</i> We've lost engine number one!

3
00:00:09,000 --> 00:00:11,500
(Groaning)
Hold on, everyone!
"""
    full, preview = TranscriptService.clean_subtitle_text(sample_srt)
    assert "Dramatic music" not in full
    assert "Groaning" not in full
    assert "00:00:01" not in full
    assert "Mayday, mayday! We've lost engine number one! Hold on, everyone!" in full


def test_language_resolution():
    from backend.app.services.verification_engine import resolve_language_code
    assert resolve_language_code("English") == "en"
    assert resolve_language_code("Japanese") == "ja"
    assert resolve_language_code("Korean") == "ko"
    assert resolve_language_code("fr") == "fr"
    assert resolve_language_code("") == "en"


@pytest.mark.asyncio
async def test_audit_endpoint(test_db):
    from unittest.mock import patch, AsyncMock
    from backend.app.models.show import Show
    app.dependency_overrides[get_db] = lambda: test_db

    show = Show(
        sonarr_series_id=999,
        title="Test Audit Show",
        year=2024,
        original_language="English"
    )
    test_db.add(show)
    await test_db.commit()

    with patch("backend.app.services.verification_engine.VerificationEngine.run_show_verification", new_callable=AsyncMock):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(f"/api/v1/shows/{show.id}/audit")
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert "job_id" in data

    app.dependency_overrides.clear()
