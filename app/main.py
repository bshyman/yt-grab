import asyncio
import hashlib
import hmac
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import youtube
from .config import Settings, load_settings
from .converters import build_chain
from .db import DB
from .jobs import JobQueue
from .meta import safe_name

log = logging.getLogger(__name__)

STATIC = Path(__file__).parent / "static"
COOKIE = "ytg_admin"
_PUBLIC_FIELDS = ("id", "video_id", "title", "artist", "mode", "status", "progress", "error", "created_at")


class JobIn(BaseModel):
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    mode: Literal["device", "library"] = "device"
    title: str | None = Field(default=None, max_length=300)


class LoginIn(BaseModel):
    password: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db = DB(settings.data_dir / "yt-grab.db")
    queue = JobQueue(db, settings, build_chain(settings))
    admin_token = (
        hmac.new(settings.admin_password.encode(), b"ytg-admin", hashlib.sha256).hexdigest()
        if settings.admin_password
        else None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await queue.start()
        yield
        await queue.stop()

    app = FastAPI(title="yt-grab", lifespan=lifespan, docs_url=None, redoc_url=None)

    def who(request: Request) -> str:
        # Tailscale Serve stamps the caller's login. LAN hits fall back to IP
        login = request.headers.get("tailscale-user-login")
        if login:
            return login
        fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        return fwd or (request.client.host if request.client else "unknown")

    def is_admin(request: Request) -> bool:
        return bool(admin_token) and hmac.compare_digest(
            request.cookies.get(COOKIE, "").encode(), admin_token.encode()
        )

    def used_today(owner: str) -> int:
        return db.count_since(owner, time.time() - 86400)

    def public(job: dict) -> dict:
        return {k: job[k] for k in _PUBLIC_FIELDS} | {
            "has_file": job["mode"] == "device" and job["status"] == "done",
        }

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/api/me")
    def me(request: Request):
        owner = who(request)
        return {
            "user": owner,
            "admin": is_admin(request),
            "daily_limit": settings.daily_limit,
            "used_today": used_today(owner),
            "library": settings.library_enabled,
        }

    @app.post("/api/login")
    async def login(body: LoginIn, response: Response):
        if not admin_token or not hmac.compare_digest(body.password.encode(), settings.admin_password.encode()):
            await asyncio.sleep(1)  # slow down guessing
            raise HTTPException(401, "wrong password")
        # not Secure on purpose, LAN access is plain http
        response.set_cookie(COOKIE, admin_token, max_age=365 * 86400, httponly=True, samesite="lax")
        return {"ok": True}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.get("/api/search")
    async def search(q: str):
        q = q.strip()
        if not q:
            raise HTTPException(400, "empty query")
        if youtube.is_youtube_url(q):
            vid = youtube.extract_video_id(q)
            if not vid:
                raise HTTPException(400, "couldn't find a video in that link (playlists aren't supported yet)")
            return {"results": [await youtube.lookup(vid)]}
        try:
            results = await asyncio.to_thread(youtube.search, q[:200])
        except Exception as e:
            log.exception("search failed")
            raise HTTPException(502, f"search failed: {e}") from e
        return {"results": results}

    # async so queue.submit runs on the event loop thread, asyncio.Queue isn't thread-safe
    @app.post("/api/jobs")
    async def create_job(body: JobIn, request: Request):
        owner, admin = who(request), is_admin(request)
        if body.mode == "library":
            if not admin:
                raise HTTPException(403, "only the admin can add to the library")
            if not settings.library_enabled:
                raise HTTPException(400, "no music library mounted")
        if not admin and settings.daily_limit and used_today(owner) >= settings.daily_limit:
            raise HTTPException(429, f"daily limit hit ({settings.daily_limit}/day)")

        max_duration = None if admin else (settings.max_duration_min * 60 or None)
        job = db.create_job(owner, body.video_id, body.mode, body.title, max_duration)
        queue.submit(job["id"])
        return public(job)

    @app.get("/api/jobs")
    def list_jobs(request: Request):
        return {"jobs": [public(j) for j in db.list_for(who(request))]}

    @app.get("/api/jobs/{job_id}/file")
    def download(job_id: str, request: Request):
        job = db.get(job_id)
        # 404 rather than 403 so job ids can't be probed
        if not job or (job["owner"] != who(request) and not is_admin(request)):
            raise HTTPException(404, "not found")
        if not (job["mode"] == "device" and job["status"] == "done" and job["file_path"]):
            raise HTTPException(404, "no file for this job")
        path = Path(job["file_path"])
        if not path.is_file():
            raise HTTPException(410, "file expired")
        name = safe_name(job["title"] or job["video_id"])
        if job["artist"]:
            name = f"{safe_name(job['artist'])} - {name}"
        return FileResponse(path, media_type="audio/mpeg", filename=f"{name}.mp3")

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
