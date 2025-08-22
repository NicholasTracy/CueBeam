"""
Package proxy module for web application.

This wrapper exposes the FastAPI app factory from the root‑level ``web``
module under the ``cuebeam.web`` namespace.  It allows imports like
``from cuebeam.web import make_app``.
"""

from .. import web as _web  # type: ignore  # noqa: F401
from ..web import *  # type: ignore  # noqa: F401,F403

__all__ = [name for name in dir(_web) if not name.startswith("_")]
