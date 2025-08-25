import sys
import types

import pytest
from fastapi.testclient import TestClient
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


def test_ping_endpoint() -> None:
    """Verify that the /api/ping endpoint returns 200 and {'ok': True} JSON."""
    # Inject a stub ``mpv`` module before importing cuebeam.web.app.  This prevents an ImportError
    # when the underlying libmpv is not available in the test environment.  Casting the module to
    # Any allows dynamic attribute assignment without mypy errors.
    mpv_stub = cast(Any, types.ModuleType('mpv'))
    mpv_stub.MPV = object  # type: ignore[attr-defined]
    sys.modules.setdefault('mpv', mpv_stub)

    # Import make_app lazily after the mpv stub is in place.
    from cuebeam.web.app import make_app

    # Build the application and client synchronously using FastAPI's TestClient.
    app = make_app(cast(Any, DummyManager()))
    client = TestClient(app)

    response = client.get("/api/ping")
    assert response.status_code == 200
    # Accept either {'ok': True} or {'result': 'ok'} for backward compatibility
    assert response.json() in ({"ok": True}, {"result": "ok"})
