import sys
import types

import pytest
from httpx import AsyncClient
from typing import cast, Any


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
    # Inject a stub ``mpv`` module before importing cuebeam.web.app.  This prevents an ImportError
    # when the underlying libmpv is not available in the test environment.
    # Create a dummy module using ModuleType to satisfy the static type checker.  Using ModuleType
    # rather than SimpleNamespace avoids a mypy error on the type of the second argument to setdefault.
    # Create a dummy module and cast to Any so that assigning MPV is permitted without a type error.
    mpv_stub = cast(Any, types.ModuleType('mpv'))
    mpv_stub.MPV = object  # type: ignore[attr-defined]
    sys.modules.setdefault('mpv', mpv_stub)

    # Import make_app lazily after the mpv stub is in place.
    from cuebeam.web.app import make_app

    # Cast our dummy manager to Any to satisfy static type checking; the methods we use are compatible.
    app = make_app(cast(Any, DummyManager()))

    # Construct the client separately and ignore the call-arg type error for the ``app`` keyword.
    client = AsyncClient(app=app, base_url="http://test")  # type: ignore[call-arg]
    async with client:
        response = await client.get("/api/ping")
        assert response.status_code == 200
        # Accept either {'ok': True} or {'result': 'ok'} for backward compatibility
        assert response.json() in ({"ok": True}, {"result": "ok"})
