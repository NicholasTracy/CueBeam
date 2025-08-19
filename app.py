import logging
import sys
from pathlib import Path

import uvicorn

from control import ControlManager
from playback import PlaybackManager
from web import make_app

ROOT = Path(__file__).parent.resolve()
LOG_PATH = ROOT / "cuebeam.log"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    mgr = PlaybackManager()
    mgr.start()

    ctrl = ControlManager(mgr.cfg, on_event=mgr.trigger_event)
    ctrl.start()

    app = make_app(mgr)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_config=None)


if __name__ == "__main__":
    main()
