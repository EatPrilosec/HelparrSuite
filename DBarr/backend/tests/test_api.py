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
        assert data["sonarr_url"] == "http://localhost:8989"

        # Update settings
        update_res = await client.post(
            "/api/v1/settings",
            json={"settings": {"sonarr_url": "http://192.168.8.56:8989", "sonarr_api_key": "test_key"}}
        )
        assert update_res.status_code == 200

        # Verify updated settings
        res2 = await client.get("/api/v1/settings")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["sonarr_url"] == "http://192.168.8.56:8989"
        assert data2["sonarr_api_key"] == "test_key"

    app.dependency_overrides.clear()
