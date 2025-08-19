import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional

import bcrypt
import yaml
from fastapi import (
    Depends,
    FastAPI,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

ROOT = Path(__file__).parent.resolve()
MEDIA_DIR = ROOT / "media"
IDLE_DIR = MEDIA_DIR / "idle"
EVENTS_DIR = MEDIA_DIR / "events"
RANDOM_DIR = MEDIA_DIR / "random"
CONFIG_PATH = ROOT / "config" / "config.yaml"
LOG_PATH = ROOT / "cuebeam.log"


def _signer(secret: str) -> TimestampSigner:
    return TimestampSigner(secret)


def _get_cookie(request: Request, cfg: dict) -> str:
    name = (cfg.get("auth") or {}).get("cookie_name") or "cuebeam_session"
    return request.cookies.get(name, "")


def _require_auth(cfg: dict):
    def dep(request: Request) -> bool:
        auth_cfg = cfg.get("auth") or {}
        if not auth_cfg.get("enabled", False):
            return True

        cookie = _get_cookie(request, cfg)
        if not cookie:
            raise HTTPException(401)

        signer = _signer(auth_cfg.get("cookie_secret") or "change-me")
        ttl = int(auth_cfg.get("session_ttl_minutes", 1440)) * 60
        try:
            signer.unsign(cookie, max_age=ttl)
            return True
        except (BadSignature, SignatureExpired) as exc:  # noqa: PERF203
            raise HTTPException(401) from exc

    return dep


def make_app(manager) -> FastAPI:
    app = FastAPI(title="CueBeam")
    templates = Jinja2Templates(directory=str(ROOT / "templates"))
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    def save_cfg(cfg: dict) -> None:
        CONFIG_PATH.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        manager.reload_config()

    def auth_enabled() -> bool:
        return (manager.cfg.get("auth") or {}).get("enabled", False)

    require_auth = _require_auth(manager.cfg)

    # ---- auth ------------------------------------------------------------

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request) -> HTMLResponse:
        ctx = {"request": request, "enabled": auth_enabled()}
        return templates.TemplateResponse("login.html", ctx)

    @app.post("/login")
    async def do_login(request: Request, password: str = Form(...)) -> RedirectResponse:
        a = manager.cfg.get("auth") or {}
        if not a.get("enabled", False):
            return RedirectResponse("/", status_code=303)

        pw_hash = (a.get("password_hash") or "").encode()
        if not pw_hash or not bcrypt.checkpw(password.encode(), pw_hash):
            return RedirectResponse("/login", status_code=303)

        signer = _signer(a.get("cookie_secret") or "change-me")
        token = signer.sign(b"ok").decode()
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(
            a.get("cookie_name") or "cuebeam_session",
            token,
            httponly=True,
            samesite="lax",
        )
        return resp

    @app.post("/logout")
    async def do_logout() -> RedirectResponse:
        a = manager.cfg.get("auth") or {}
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(a.get("cookie_name") or "cuebeam_session")
        return resp

    # ---- UI --------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            "index.html", {"request": request, "auth_enabled": auth_enabled()}
        )

    @app.post("/action", dependencies=[Depends(require_auth)])
    async def action(cmd: str = Form(...)) -> RedirectResponse:
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
        return RedirectResponse("/", status_code=303)

    @app.get("/settings", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def settings(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("settings.html", {"request": request, "cfg": manager.cfg})

    @app.post("/settings/update", dependencies=[Depends(require_auth)])
    async def settings_update(
        idle_to_random_seconds: int = Form(...),
        daily_shutdown_time: str = Form(""),
        audio_output_device: str = Form(""),
        trigger_source: str = Form("gpio"),
        gpio_pin: int = Form(17),
        gpio_pull: str = Form("up"),
        gpio_edge: str = Form("falling"),
        gpio_db_ms: int = Form(50),
        artnet_universe: int = Form(0),
        artnet_channel: int = Form(1),
        artnet_threshold: int = Form(128),
        sacn_universe: int = Form(1),
        sacn_channel: int = Form(1),
        sacn_threshold: int = Form(128),
        auth_enabled_f: Optional[str] = Form(None),
        auth_password: str = Form(""),
        cookie_secret: str = Form(""),
        preferred_mac: str = Form(""),
        bt_scan_seconds: int = Form(8),
    ) -> RedirectResponse:
        cfg = manager.cfg

        cfg["idle_to_random_seconds"] = int(idle_to_random_seconds)
        cfg["daily_shutdown_time"] = daily_shutdown_time.strip()
        cfg["audio_output_device"] = audio_output_device.strip()
        cfg["trigger_source"] = trigger_source.strip().lower()

        cfg["gpio"] = {
            "pin": int(gpio_pin),
            "pull": gpio_pull,
            "edge": gpio_edge,
            "debounce_ms": int(gpio_db_ms),
        }

        cfg["artnet"] = {
            "listen_host": (cfg.get("artnet", {}) or {}).get("listen_host", "0.0.0.0"),
            "port": int((cfg.get("artnet", {}) or {}).get("port", 6454)),
            "universe": int(artnet_universe),
            "channel": int(artnet_channel),
            "threshold": int(artnet_threshold),
        }

        cfg["sacn"] = {
            "universe": int(sacn_universe),
            "channel": int(sacn_channel),
            "threshold": int(sacn_threshold),
        }

        enabled = auth_enabled_f == "on"
        cfg["auth"] = cfg.get("auth") or {}
        cfg["auth"]["enabled"] = enabled

        if cookie_secret.strip():
            cfg["auth"]["cookie_secret"] = cookie_secret.strip()

        if auth_password.strip():
            cfg["auth"]["password_hash"] = bcrypt.hashpw(
                auth_password.encode(), bcrypt.gensalt()
            ).decode()

        cfg["bluetooth"] = cfg.get("bluetooth") or {}
        cfg["bluetooth"]["preferred_mac"] = preferred_mac.strip()
        cfg["bluetooth"]["scan_seconds"] = int(bt_scan_seconds)

        save_cfg(cfg)
        return RedirectResponse("/settings", status_code=303)

    @app.get("/logs", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def logs(request: Request) -> HTMLResponse:
        text = LOG_PATH.read_text(encoding="utf-8") if LOG_PATH.exists() else ""
        return templates.TemplateResponse("logs.html", {"request": request, "logtext": text})

    @app.post("/upload", dependencies=[Depends(require_auth)])
    async def upload(file: UploadFile, target: str = Form(...)) -> RedirectResponse:
        targets = {"idle": IDLE_DIR, "events": EVENTS_DIR, "random": RANDOM_DIR}
        dst = targets.get(target, IDLE_DIR)
        dst.mkdir(parents=True, exist_ok=True)

        with (dst / file.filename).open("wb") as f:
            shutil.copyfileobj(file.file, f)

        return RedirectResponse("/", status_code=303)

    # ---- APIs ------------------------------------------------------------

    @app.get("/api/status", dependencies=[Depends(require_auth)])
    async def api_status() -> JSONResponse:
        return JSONResponse(manager.status())

    # ---- Bluetooth pages -------------------------------------------------

    from bt import pair_trust_connect, paired_devices, scan  # local import

    @app.get("/bt/list", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def bt_list(request: Request) -> HTMLResponse:
        bcfg = manager.cfg.get("bluetooth") or {}
        devices = scan(int(bcfg.get("scan_seconds", 8)))
        paired = paired_devices()
        ctx = {
            "request": request,
            "devices": devices,
            "paired": paired,
            "preferred": (bcfg.get("preferred_mac") or ""),
        }
        return templates.TemplateResponse("bt.html", ctx)

    @app.post("/bt/connect", dependencies=[Depends(require_auth)])
    async def bt_connect(
        mac: str = Form(...), save_as_preferred: Optional[str] = Form(None)
    ) -> RedirectResponse:
        ok = pair_trust_connect(mac)
        if ok and save_as_preferred == "on":
            cfg = manager.cfg
            cfg["bluetooth"] = cfg.get("bluetooth") or {}
            cfg["bluetooth"]["preferred_mac"] = mac
            save_cfg(cfg)
        return RedirectResponse("/bt/list", status_code=303)

    # ---- WebSocket -------------------------------------------------------

    def _ws_cookie_ok(cookies: dict) -> bool:
        a = manager.cfg.get("auth") or {}
        if not a.get("enabled", False):
            return True

        name = a.get("cookie_name") or "cuebeam_session"
        token = cookies.get(name)
        if not token:
            return False

        signer = _signer(a.get("cookie_secret") or "change-me")
        ttl = int(a.get("session_ttl_minutes", 1440)) * 60
        try:
            signer.unsign(token, max_age=ttl)
            return True
        except (BadSignature, SignatureExpired):
            return False

    @app.websocket("/ws/status")
    async def ws_status(ws: WebSocket) -> None:
        if not _ws_cookie_ok(ws.cookies):
            await ws.close(code=4401)
            return

        await ws.accept()
        try:
            while True:
                await ws.send_text(json.dumps(manager.status()))
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            return

    return app
