import pytest


@pytest.mark.asyncio(loop_scope="session")
async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] in ("connected", "disconnected")


@pytest.mark.asyncio(loop_scope="session")
async def test_data_status(client):
    resp = await client.get("/api/v1/data/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_races" in data
    assert "total_entries" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_races_list(client):
    resp = await client.get("/api/v1/races")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_race_not_found(client):
    resp = await client.get("/api/v1/races/nonexistent")
    assert resp.status_code == 404
