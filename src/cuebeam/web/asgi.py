"""
ASGI entrypoint for CueBeam.

This module configures logging, instantiates the core managers and
provides the ``app`` object for use by ASGI servers such as
``uvicorn``.  It should be executed via ``uvicorn --app-dir src
cuebeam.web.asgi:app`` when the project is installed in a layout
where ``cuebeam`` lives under ``src``.  The :mod:`logging` module is
configured to write rotating log files into the ``logs`` directory
relative to the project root.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ..playback import PlaybackManager
from ..control import ControlManager
from .app import make_app


# Determine project root.  This file is located at src/cuebeam/web/asgi.py;
# the project root is three parents up.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Configure logging to a rotating file in the logs directory
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

handler = RotatingFileHandler(
    LOG_DIR / "cuebeam.log",
    maxBytes=1_500_000,
    backupCount=3,
)
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(fmt)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)


# Instantiate managers
mgr = PlaybackManager()
mgr.start()


def _handle_event() -> None:
    _ = mgr.trigger_event()


ctrl = ControlManager(mgr.cfg, on_event=_handle_event)
ctrl.start()

# Export FastAPI application
app = make_app(mgr)
