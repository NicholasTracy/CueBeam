from pathlib import Path
import shutil
import logging

from fastapi import FastAPI, HTTPException, Request, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from playback import PlaybackManager  # type: ignore

# Set up a module‑specific logger.  Using the logging module instead of print
# statements provides structured, configurable logging across the application.
logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).parent.resolve()
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
STATIC_DIR = BASE_DIR / "static"


def make_app(manager: PlaybackManager) -> FastAPI:
    app = FastAPI()

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        now_playing = None
        if hasattr(manager, "now_playing"):
            now_playing = manager.now_playing()
        status = {"now_playing": now_playing}
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "status": status},
        )

    @app.post("/upload")
    async def upload(request: Request, file: UploadFile, category: str = Form("idle")):
        """
        Save upload to media/<category>, rescan, and for 'idle' start playing.
        """
        cats = {"idle", "event", "random"}
        if category not in cats:
            raise HTTPException(status_code=400, detail="Invalid category")

        dest_dir = BASE_DIR / "media" / category
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Only use the basename of the uploaded filename to avoid path traversal
        # attacks (e.g. filenames containing "../").  Path().name strips any
        # directory separators.  See OWASP guidance on path traversal【714359060419038†L60-L69】.
        safe_name = Path(file.filename).name
        dest_path = dest_dir / safe_name
        try:
            with dest_path.open("wb") as out_f:
                shutil.copyfileobj(file.file, out_f)
        finally:
            await file.close()

        try:
            if hasattr(manager, "reload_media"):
                manager.reload_media()
            if category == "idle" and hasattr(manager, "ensure_idle_playing"):
                manager.ensure_idle_playing()
        except Exception as exc:  # noqa: BLE001
            # Upload succeeded; library update failed.
            return JSONResponse(
                {"ok": False, "message": f"Uploaded; reload failed: {exc}"},
                status_code=202,
            )

        return RedirectResponse(url="/?msg=uploaded", status_code=303)

    @app.post("/api/reload")
    async def api_reload():
        if hasattr(manager, "reload_media"):
            manager.reload_media()
            return {"ok": True}
        raise HTTPException(status_code=500, detail="reload_media missing")

    @app.post("/api/ensure_idle")
    async def api_ensure_idle():
        if hasattr(manager, "ensure_idle_playing"):
            manager.ensure_idle_playing()
            return {"ok": True}
        raise HTTPException(status_code=500, detail="ensure_idle_playing missing")

    @app.get("/api/ping")
    async def ping():
        return {"ok": True}

    return app
