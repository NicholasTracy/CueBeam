"""
CueBeam core package.

This package provides namespaced imports for the main CueBeam modules.
Importing from ``cuebeam`` ensures that imports resolve correctly even when
the project adopts a package layout.  It simply re‑exports the existing
modules from the repository root so that legacy imports continue to work.
"""

from ..playback import PlaybackManager  # noqa: F401  (re‑export)
from ..control import ControlManager  # noqa: F401  (re‑export)
from ..bt import scan, pair_trust_connect, ensure_connected  # noqa: F401  (re‑export)
