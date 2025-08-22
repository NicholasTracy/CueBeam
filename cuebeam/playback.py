"""
Package proxy module for playback.

This thin wrapper forwards all public attributes from the root‑level
``playback`` module into the ``cuebeam.playback`` namespace.  It allows
importing ``cuebeam.playback`` without moving the underlying implementation.
"""

from .. import playback as _playback  # type: ignore  # noqa: F401

# re‑export every public name from the root module
from ..playback import *  # type: ignore  # noqa: F401,F403

__all__ = [name for name in dir(_playback) if not name.startswith("_")]
