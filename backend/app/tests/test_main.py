import pytest
from app.main import app
from httpx import AsyncClient


@pytest.mark.anyio
async def test_get_all_naics_codes():
    async with AsyncClient(app=app, base_url="http://localhost:8000") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)
