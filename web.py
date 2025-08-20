import asyncio
import secrets
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Callable

from fastapi import FastAPI, Request, Form, Depends, UploadFile, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
import yaml

from playback import PlaybackManager, CONFIG_PATH, IDLE_DIR, EVENTS_DIR, RANDOM_DIR
from bt import scan, pair_trust_connect

ROOT = Path(__file__).parent.resolve()
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

def _require_auth(cfg: Dict[str, Any]) -> Callable:
    a = cfg.get("auth") or {}
    enabled = bool(a.get("enabled"))
    cookie_name = a.get("cookie_name") or "cuebeam_session"
    secret = a.get("cookie_secret") or ""

    def _dep(request: Request) -> None:
        if not enabled:
            return
        token = request.cookies.get(cookie_name)
        if not token or (secret and token != secret):
            # redirect to login
            raise RedirectResponse("/login")
    return _dep

def make_app(manager: PlaybackManager) -> FastAPI:
    templates = env
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    require_auth = _require_auth(manager.cfg)

    # pages

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        tpl = templates.get_template("index.html")
        return HTMLResponse(tpl.render(request=request))

    @app.get("/settings", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def settings(request: Request):
        tpl = templates.get_template("settings.html")
        return HTMLResponse(tpl.render(request=request, cfg=manager.cfg))

    @app.post("/settings/update", dependencies=[Depends(require_auth)])
    async def settings_update(
        idle_to_random_seconds: int = Form(60),
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
        sact=Form(""),
        sacn_universe: int = Form(1),
        sacn_channel: int = Form(1),
        sacn_threshold: int = Form(128),
        auth_enabled_f: str | None = Form(None),
        auth_password: str = Form(""),
        cookie_secret: str = Form(""),
        preferred_mac: str = Form(""),
        bt_scan_seconds: int = Form(8),
    ) -> RedirectResponse:
        cfg = manager.cfg
        cfg["idle_to_random_seconds"] = int(idle_to_random_seconds)
        cfg["daily_shutdown_time"] = (daily_shutdown_time or "").strip()
        cfg["audio_output_device"] = (audio_output_device or "").strip()
        cfg["trigger_source"] = (trigger_source or "gpio").lower()
        cfg["gpio"] = {"pin": int(gpio_pin), "pull": gpio_pull, "edge": gpio_edge, "debounce_ms": int(gpio_db_ms)}
        cfg["artnet"] = {"listen_host": "0.0.0.0", "port": 6454, "universe": int(artnet_universe), "channel": int(artnet_channel), "threshold": int(artnet_threshold)}
        cfg["sacn"] = {"universe": int(sacn_universe), "channel": int(sacn_channel), "threshold": int(sacn_threshold)}
        cfg["bluetooth"] = {"preferred_mac": preferred_mac.strip(), "scan_seconds": int(bt_scan_seconds)}
        cfg["auth"] = cfg.get("auth") or {}
        cfg["auth"]["enabled"] = bool(auth_enabled_f)
        if cfg["auth"]["enabled"] and auth_password:
            cfg["auth"]["cookie_secret"] = auth_password
        if cfg["auth"]["enabled"] and not cfg["auth"].get("cookie_secret"):
            cfg["auth"]["cookie_secret"] = secrets.token_urlsafe(32)
        CONFIG_PATH.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        manager.reload_config()
        return RedirectResponse("/settings", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        tpl = templates.get_template("login.html")
        return HTMLResponse(tpl.render(request=request))

    @app.post("/login")
    async def login(request: Request, password: str = Form(...)) -> RedirectResponse:
        a = manager.cfg.get("auth") or {}
        if not a.get("enabled"):
            return RedirectResponse("/", status_code=303)
        cookie_name = a.get("cookie_name") or "cuebeam_session"
        secret = a.get("cookie_secret") or ""
        resp = RedirectResponse("/", status_code=303)
        if secret and password == secret:
            resp.set_cookie(cookie_name, secret, httponly=True, samesite="lax", secure=False)
        return resp

    # actions

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

    @app.post("/upload", dependencies=[Depends(require_auth)])
    async def upload(file: UploadFile, target: str = Form(...)) -> RedirectResponse:
        targets = {"idle": IDLE_DIR, "events": EVENTS_DIR, "random": RANDOM_DIR}
        dst = targets.get(target, IDLE_DIR)
        dst.mkdir(parents=True, exist_ok=True)
        try:
            safe_name = PurePosixPath(file.filename).name
            if not safe_name:
                return RedirectResponse("/?msg=upload_failed", status_code=303)
            with (dst / safe_name).open("wb") as f:
                shutil.copyfileobj(file.file, f)
            return RedirectResponse("/?msg=uploaded", status_code=303)
        except Exception:
            return RedirectResponse("/?msg=upload_failed", status_code=303)

    # status API + websocket

    @app.get("/api/status")
    async def api_status() -> JSONResponse:
        return JSONResponse(manager.status())

    @app.websocket("/ws/status")
    async def ws_status(ws: WebSocket) -> None:
        await ws.accept()
        try:
            while True:
                await ws.send_json(manager.status())
                await asyncio.sleep(0.5)
        except Exception:
            return

    # bluetooth pages

    @app.get("/bt/list", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def bt_list(request: Request):
        tpl = templates.get_template("bt.html")
        # for static display; JSON endpoints do the live scan/connect
        try:
            paired = scan(2)  # quick pass-through (best-effort)
        except Exception:
            paired = []
        return HTMLResponse(tpl.render(request=request, devices=[], paired=paired))

    @app.get("/bt/scan_json", dependencies=[Depends(require_auth)])
    async def bt_scan_json() -> JSONResponse:
        secs = int((manager.cfg.get("bluetooth") or {}).get("scan_seconds", 8))
        try:
            devices = await asyncio.to_thread(scan, secs)
            return JSONResponse({"ok": True, "duration": secs, "devices": devices})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @app.post("/bt/connect_json", dependencies=[Depends(require_auth)])
    async def bt_connect_json(mac: str = Form(...), save_as_preferred: str | None = Form(None)) -> JSONResponse:
        try:
            ok = await asyncio.to_thread(pair_trust_connect, mac)
            if ok and save_as_preferred == "on":
                cfg = manager.cfg
                cfg["bluetooth"] = cfg.get("bluetooth") or {}
                cfg["bluetooth"]["preferred_mac"] = mac
                CONFIG_PATH.write_text(yaml.safe_dump(cfg), encoding="utf-8")
                manager.reload_config()
            return JSONResponse({"ok": bool(ok)})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    # logs page (journal/file)
    @app.get("/logs", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def logs_page(request: Request):
        log_path = Path("logs") / "cuebeam.log"
        text = log_path.read_text(encoding="utf-8")[-100_000:] if log_path.exists() else "(no logs yet)"
        tpl = env.get_template("logs.html")
        return HTMLResponse(tpl.render(request=request, logtext=text))

    return app
