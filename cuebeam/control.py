"""
Package proxy module for control.

This wrapper forwards names from the root‑level ``control`` module into
the ``cuebeam.control`` namespace.
"""

from .. import control as _control  # type: ignore  # noqa: F401
from ..control import *  # type: ignore  # noqa: F401,F403

__all__ = [name for name in dir(_control) if not name.startswith("_")]
