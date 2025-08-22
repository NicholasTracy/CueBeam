"""
CueBeam package root.

This namespace exposes the primary classes and factory functions for
CueBeam.  Import :class:`PlaybackManager` and :class:`ControlManager`
from here to manage media playback and triggers, and use
``from cuebeam.web import make_app`` to construct the FastAPI
application.
"""

from .playback import PlaybackManager  # noqa: F401
from .control import ControlManager  # noqa: F401

__all__ = [
    "PlaybackManager",
    "ControlManager",
]
