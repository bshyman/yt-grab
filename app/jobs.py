import asyncio
import logging
import shutil
import time
from pathlib import Path

from . import plex
from .config import Settings
from .converters import ConvertError, Converter, convert
from .db import DB
from .meta import TrackMeta, parse_title, safe_name
from .tagging import tag_mp3

log = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, db: DB, settings: Settings, chain: list[Converter]):
        self.db = db
        self.settings = settings
        self.chain = chain
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    @property
    def _workdir(self) -> Path:
        return self.settings.data_dir / "work"

    async def start(self) -> None:
        # whatever's in here is from a dead process
        shutil.rmtree(self._workdir, ignore_errors=True)
        for _ in range(max(1, self.settings.max_concurrent)):
            self._tasks.append(asyncio.create_task(self._worker()))
        self._tasks.append(asyncio.create_task(self._janitor()))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    def submit(self, job_id: str) -> None:
        self._queue.put_nowait(job_id)

    async def _worker(self) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await asyncio.to_thread(self._run, job_id)
            finally:
                self._queue.task_done()

    def _run(self, job_id: str) -> None:
        job = self.db.get(job_id)
        if not job:
            return
        self.db.update(job_id, status="running")
        work = self._workdir / job_id
        work.mkdir(parents=True, exist_ok=True)

        last = 0.0

        def progress(p: float) -> None:
            nonlocal last
            # yt-dlp fires this constantly, don't hammer sqlite
            if abs(p - last) >= 0.02 or p >= 1:
                last = p
                self.db.update(job_id, progress=round(p, 3))

        try:
            res = convert(self.chain, job["video_id"], work, progress, job["max_duration"])
            meta = parse_title(res.title, res.channel, res.artist, res.track, res.album)
            tagged = work / "out.mp3"
            tag_mp3(res.path, tagged, meta, res.thumbnails)

            if job["mode"] == "library":
                dest = self._library_path(meta)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(tagged, dest)
                plex.refresh(self.settings, dest.parent)
            else:
                dest = self.settings.data_dir / "downloads" / f"{job_id}.mp3"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(tagged, dest)

            self.db.update(
                job_id, status="done", progress=1.0, title=meta.title, artist=meta.artist,
                file_path=str(dest), finished_at=time.time(),
            )
        except Exception as e:
            log.exception("job %s failed", job_id)
            msg = str(e) if isinstance(e, ConvertError) else f"{type(e).__name__}: {e}"
            self.db.update(job_id, status="error", error=msg[:500], finished_at=time.time())
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def _library_path(self, meta: TrackMeta) -> Path:
        # Plex wants Artist/Album/Track
        base = self.settings.music_dir
        if self.settings.library_subdir:
            base = base / safe_name(self.settings.library_subdir)
        return base / safe_name(meta.artist) / safe_name(meta.album) / f"{safe_name(meta.title)}.mp3"

    async def _janitor(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self._sweep)
            except Exception:
                log.exception("cleanup failed")
            await asyncio.sleep(3600)

    def _sweep(self) -> None:
        cutoff = time.time() - self.settings.file_ttl_hours * 3600
        for job in self.db.expired_downloads(cutoff):
            if job["file_path"]:
                Path(job["file_path"]).unlink(missing_ok=True)
            self.db.update(job["id"], status="expired", file_path=None)
