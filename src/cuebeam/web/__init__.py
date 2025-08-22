"""
Web subpackage for CueBeam.

This package exposes the FastAPI application factory and ASGI entrypoint.
Use :func:`make_app` to construct an application instance bound to a
``PlaybackManager``.
"""

from .app import make_app  # noqa: F401

__all__ = ["make_app"]