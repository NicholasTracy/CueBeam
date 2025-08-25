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

# Additional imports for configuration management and Bluetooth helpers
import yaml
from .. import bt


# Module‑level logger
logger = logging.getLogger(__name__)

# Compute the project root three levels up (src/cuebeam/web/app.py -> web -> cuebeam -> src)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Template and static directories relative to project root
TEMPLATES = Jinja2Templates(directory=str(PROJECT_ROOT / "templates"))
STATIC_DIR = PROJECT_ROOT / "static"

# Path to the YAML configuration file.  Used when persisting settings.
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


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
        # Sanitize filename and ensure extension is allowed
        # ``UploadFile.filename`` may be ``None``, so fall back to empty string to satisfy type check
        safe_name = Path(file.filename or "").name
        dest_path = dest_dir / safe_name
        # Validate file extension – allow common video formats
        allowed_ext = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".mpg", ".mpeg", ".ogg"}
        if dest_path.suffix.lower() not in allowed_ext:
            # Close the file handle and redirect with error message
            await file.close()
            return RedirectResponse(url="/?msg=invalidfile", status_code=303)
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

    # ------------------------------------------------------------------
    # Settings and configuration routes
    # ------------------------------------------------------------------

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        """Render the settings page with the current configuration."""
        return TEMPLATES.TemplateResponse(
            "settings.html",
            {"request": request, "cfg": manager.cfg},
        )

    @app.post("/settings/update")
    async def settings_update(
        request: Request,
        idle_to_random_seconds: int = Form(...),
        daily_shutdown_time: str = Form(""),
        audio_output_device: str = Form(""),
        trigger_source: str = Form(...),
        gpio_pin: int = Form(...),
        gpio_pull: str = Form(...),
        gpio_edge: str = Form(...),
        gpio_db_ms: int = Form(...),
        artnet_universe: int = Form(...),
        artnet_channel: int = Form(...),
        artnet_threshold: int = Form(...),
        sacn_universe: int = Form(...),
        sacn_channel: int = Form(...),
        sacn_threshold: int = Form(...),
        auth_enabled_f: str | None = Form(None),
        auth_password: str = Form(""),
        preferred_mac: str | None = Form(None),
        bt_scan_seconds: int | None = Form(None),
    ):
        """Update the configuration from the submitted settings form.

        The values are saved back into the manager's configuration, written
        to the YAML file and then reloaded via the manager.
        """
        cfg = manager.cfg
        # General settings
        cfg["idle_to_random_seconds"] = int(idle_to_random_seconds)
        cfg["daily_shutdown_time"] = daily_shutdown_time or ""
        cfg["audio_output_device"] = audio_output_device or ""
        # Trigger source
        cfg["trigger_source"] = trigger_source
        # GPIO
        gpio_cfg = cfg.setdefault("gpio", {})
        gpio_cfg["pin"] = int(gpio_pin)
        gpio_cfg["pull"] = gpio_pull
        gpio_cfg["edge"] = gpio_edge
        gpio_cfg["debounce_ms"] = int(gpio_db_ms)
        # Art-Net
        artnet_cfg = cfg.setdefault("artnet", {})
        artnet_cfg["universe"] = int(artnet_universe)
        artnet_cfg["channel"] = int(artnet_channel)
        artnet_cfg["threshold"] = int(artnet_threshold)
        # sACN
        sacn_cfg = cfg.setdefault("sacn", {})
        sacn_cfg["universe"] = int(sacn_universe)
        sacn_cfg["channel"] = int(sacn_channel)
        sacn_cfg["threshold"] = int(sacn_threshold)
        # Auth
        auth_cfg = cfg.setdefault("auth", {})
        auth_cfg["enabled"] = bool(auth_enabled_f)
        if auth_password:
            import hashlib
            auth_cfg["cookie_secret"] = hashlib.sha256(auth_password.encode()).hexdigest()
        # Bluetooth settings are not updated via this form.  Preserve existing values unless provided.
        if preferred_mac is not None:
            bt_cfg = cfg.setdefault("bluetooth", {})
            bt_cfg["preferred_mac"] = preferred_mac.strip()
        if bt_scan_seconds is not None:
            bt_cfg = cfg.setdefault("bluetooth", {})
            bt_cfg["scan_seconds"] = int(bt_scan_seconds)
        # Persist configuration
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(cfg, f)
            manager.reload_config()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to update configuration: %s", exc)
            return RedirectResponse(url="/settings?msg=error", status_code=303)
        return RedirectResponse(url="/settings?msg=saved", status_code=303)

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------
    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        """Render the logs page showing the recent log file."""
        log_file = PROJECT_ROOT / "logs" / "cuebeam.log"
        try:
            logtext = log_file.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read log file: %s", exc)
            logtext = "(log unavailable)"
        return TEMPLATES.TemplateResponse(
            "logs.html",
            {"request": request, "logtext": logtext},
        )

    # ------------------------------------------------------------------
    # Bluetooth
    # ------------------------------------------------------------------
    @app.get("/bt/list", response_class=HTMLResponse)
    async def bt_list(request: Request):
        """List known Bluetooth devices and render the Bluetooth page."""
        try:
            devices = bt.scan(timeout_sec=1)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bluetooth scan failed: %s", exc)
            devices = []
        return TEMPLATES.TemplateResponse(
            "bt.html",
            {"request": request, "paired": devices},
        )

    @app.get("/bt/scan_json")
    async def bt_scan_json():
        """Scan for Bluetooth devices and return results as JSON."""
        scan_seconds = manager.cfg.get("bluetooth", {}).get("scan_seconds", 8)
        try:
            devices = bt.scan(timeout_sec=int(scan_seconds))
            return {"ok": True, "devices": devices}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bluetooth scan failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    @app.post("/bt/connect_json")
    async def bt_connect_json(
        mac: str = Form(...),
        save_as_preferred: str | None = Form(None),
    ):
        """Attempt to pair, trust and connect to a Bluetooth device."""
        mac = mac.strip()
        if not mac:
            return {"ok": False, "error": "No MAC provided"}
        try:
            success = bt.pair_trust_connect(mac)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bluetooth connect failed: %s", exc)
            return {"ok": False, "error": str(exc)}
        if success and save_as_preferred:
            try:
                cfg = manager.cfg
                bt_cfg = cfg.setdefault("bluetooth", {})
                bt_cfg["preferred_mac"] = mac
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    yaml.safe_dump(cfg, f)
                manager.reload_config()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to save preferred MAC: %s", exc)
        return {"ok": bool(success)}

    return app
