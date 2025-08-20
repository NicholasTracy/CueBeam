import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from playback import PlaybackManager
from control import ControlManager
from web import make_app

# --- Logging to file (and console via uvicorn)
LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)
log_path = LOG_DIR / "cuebeam.log"
handler = RotatingFileHandler(log_path, maxBytes=1_500_000, backupCount=3)
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(fmt)
root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(handler)

# --- Backend boot
mgr = PlaybackManager()
mgr.start()

def _handle_event() -> None:
    _ = mgr.trigger_event()

ctrl = ControlManager(mgr.cfg, on_event=_handle_event)
ctrl.start()

# --- FastAPI app
app = make_app(mgr)
