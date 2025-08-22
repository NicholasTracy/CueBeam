import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Import from the cuebeam package to avoid relying on repository root modules.
from cuebeam import PlaybackManager, ControlManager  # type: ignore
from cuebeam.web import make_app  # type: ignore

LOG_DIR = Path("logs")
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


mgr = PlaybackManager()
mgr.start()


def _handle_event() -> None:
    _ = mgr.trigger_event()


ctrl = ControlManager(mgr.cfg, on_event=_handle_event)
ctrl.start()

app = make_app(mgr)
