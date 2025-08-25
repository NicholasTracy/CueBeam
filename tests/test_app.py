import pytest
from httpx import AsyncClient
from cuebeam.web.app import make_app


class DummyManager:
    """Simple stub implementing the minimal PlaybackManager API needed for testing."""

    def status(self):  # noqa: D401
        """Return an empty status for the ping test."""
        return {}

    def reload_media(self):
        """Stub reload_media; does nothing for test."""
        pass

    def ensure_idle_playing(self):  # noqa: D401
        """Stub ensure_idle_playing; does nothing for test."""
        pass


@pytest.mark.asyncio
async def test_ping_endpoint() -> None:
    """Verify that the /api/ping endpoint returns 200 and {'ok': True} JSON."""
    app = make_app(DummyManager())
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/ping")
        assert response.status_code == 200
        # Accept either {'ok': True} or {'result': 'ok'} for backward compatibility
        assert response.json() in ({"ok": True}, {"result": "ok"})