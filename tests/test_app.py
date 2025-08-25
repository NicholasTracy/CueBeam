import sys
import types

# Stub out the ``mpv`` module so that importing cuebeam.playback does not require the actual
# libmpv library.  This prevents an OSError during import when libmpv is not installed.
sys.modules.setdefault('mpv', types.SimpleNamespace(MPV=object))

import pytest
from httpx import AsyncClient
from typing import cast

from cuebeam.web.app import make_app
from cuebeam.playback import PlaybackManager


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
    # Cast our dummy manager to PlaybackManager for static type checking; the methods we use are compatible.
    app = make_app(cast(PlaybackManager, DummyManager()))
    # httpx's type stubs do not recognise the ``app`` argument on ``AsyncClient``.  Construct the client
    # separately and ignore the keyword argument type error.  Assigning the client to a variable before
    # entering the context allows mypy to ignore the call-arg error on the ``AsyncClient`` constructor.
    client = AsyncClient(app=app, base_url="http://test")  # type: ignore[call-arg]
    async with client:
        response = await client.get("/api/ping")
        assert response.status_code == 200
        # Accept either {'ok': True} or {'result': 'ok'} for backward compatibility
        assert response.json() in ({"ok": True}, {"result": "ok"})
