import pytest
from httpx import AsyncClient
from cuebeam.web.asgi import make_app


@pytest.mark.asyncio
async def test_ping_endpoint():
    app = make_app()
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/ping")
        assert response.status_code == 200
        assert response.json() == {"result": "ok"}
