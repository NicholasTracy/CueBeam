"""
FastAPI application for CueBeam.

This module defines :func:`make_app` which builds a FastAPI
application bound to a :class:`~cuebeam.playback.PlaybackManager`.  The
application serves a simple HTML status page, accepts media uploads and
provides several JSON and WebSocket endpoints for controlling and
monitoring playback.

The project root is determined dynamically so that templates and static
files are located correctly when the package resides under ``src``.
Uploaded filenames are sanitised by taking only ``Path(file.filename).name``
to prevent directory traversal attacks【714359060419038†L60-L69】.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

from pathlib import Path
from typing import Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    UploadFile,
    Form,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from ..playback import PlaybackManager


# Module‑level logger
logger = logging.getLogger(__name__)

# Compute the project root three levels up (src/cuebeam/web/app.py -> web -> cuebeam -> src)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Template and static directories relative to project root
TEMPLATES = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
STATIC_DIR = PROJECT_ROOT / "static"


def make_app(manager: PlaybackManager) -> FastAPI:
    """Create a FastAPI app bound to the given ``PlaybackManager``."""
    app = FastAPI()

    # Mount static file serving if the directory exists
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Render the index page with current status."""
        status = manager.status()
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "status": status},
        )

    @app.post("/upload")
    async def upload(request: Request, file: UploadFile, target: str = Form("idle")):
        """Handle an uploaded media file.

        Files are stored under ``media/<target>``.  The ``target`` must be one
        of ``idle``, ``events`` or ``random``.  Only the basename of the
        uploaded filename is used to avoid path traversal【714359060419038†L60-L69】.
        """
        cats = {"idle", "events", "random"}
        if target not in cats:
            raise HTTPException(status_code=400, detail="Invalid target category")

        dest_dir = PROJECT_ROOT / "media" / target
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize filename
        safe_name = Path(file.filename).name
        dest_path = dest_dir / safe_name
        try:
            with dest_path.open("wb") as out_f:
                content = await file.read()
                out_f.write(content)
        finally:
            await file.close()

        # After saving, reload media and ensure idle playback if necessary
        try:
            manager.reload_media()
            if target == "idle":
                manager.ensure_idle_playing()
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"ok": False, "message": f"Uploaded; reload failed: {exc}"},
                status_code=202,
            )

        return RedirectResponse(url="/?msg=uploaded", status_code=303)

    @app.post("/action")
    async def action(cmd: str = Form(...)):
        """Process a playback command from the UI form."""
        try:
            if cmd == "pause":
                manager.pause_toggle()
            elif cmd == "skip":
                manager.skip()
            elif cmd == "trigger_event":
                manager.trigger_event()
            elif cmd == "trigger_random":
                manager.trigger_random()
            elif cmd == "shutdown":
                manager.shutdown_pi()
            elif cmd == "reboot":
                manager.reboot_pi()
            else:
                raise ValueError(f"Unknown command: {cmd}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error processing command %s: %s", cmd, exc)
            return RedirectResponse(url="/?msg=error", status_code=303)
        return RedirectResponse(url="/", status_code=303)

    @app.get("/api/status")
    async def api_status():
        """Return the current playback status as JSON."""
        return manager.status()

    @app.get("/api/ping")
    async def ping():
        """Simple ping endpoint."""
        return {"ok": True}

    @app.get("/api/sysinfo")
    async def api_sysinfo():
        """Return basic system information.

        This implementation uses simple shell commands to gather host name,
        IP addresses, uptime and CPU temperature.  If a command fails the
        corresponding field may be ``null``.
        """
        hostname = socket.gethostname()
        # Get IP addresses using "hostname -I" which lists all non‑loopback
        try:
            ips_out = os.popen("hostname -I").read().strip()
            ips = [ip for ip in ips_out.split() if ip]
        except Exception:
            ips = []
        # Uptime from /proc/uptime
        uptime_s: Optional[float] = None
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                up = f.read().strip().split()[0]
                uptime_s = float(up)
        except Exception:
            uptime_s = None
        # CPU temperature (Raspberry Pi)
        cpu_temp_c: Optional[float] = None
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as f:
                t_str = f.read().strip()
                cpu_temp_c = float(t_str) / 1000.0
        except Exception:
            cpu_temp_c = None
        return {
            "hostname": hostname,
            "ips": ips,
            "uptime_s": uptime_s,
            "cpu_temp_c": cpu_temp_c,
        }

    @app.websocket("/ws/status")
    async def ws_status(websocket: WebSocket):
        """WebSocket endpoint streaming the current status every second."""
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(manager.status())
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("WebSocket error: %s", exc)
            return

    return app
