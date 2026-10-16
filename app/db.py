import sqlite3
import threading
import time
import uuid
from pathlib import Path

_SCHEMA = """
create table if not exists jobs (
    id text primary key,
    owner text not null,
    video_id text not null,
    title text,
    artist text,
    mode text not null,
    status text not null,
    progress real not null default 0,
    error text,
    file_path text,
    max_duration integer,
    created_at real not null,
    finished_at real
);
create index if not exists jobs_owner_created on jobs (owner, created_at);
"""

_UPDATABLE = {"title", "artist", "status", "progress", "error", "file_path", "finished_at"}


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)
            # anything in flight died with the last process
            self._conn.execute(
                "update jobs set status = 'error', error = 'interrupted by restart' "
                "where status in ('queued', 'running')"
            )

    def _query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock, self._conn:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def create_job(self, owner: str, video_id: str, mode: str, title: str | None, max_duration: int | None) -> dict:
        job_id = uuid.uuid4().hex
        self._query(
            "insert into jobs (id, owner, video_id, title, mode, status, max_duration, created_at) "
            "values (?, ?, ?, ?, ?, 'queued', ?, ?)",
            (job_id, owner, video_id, title, mode, max_duration, time.time()),
        )
        return self.get(job_id)

    def get(self, job_id: str) -> dict | None:
        rows = self._query("select * from jobs where id = ?", (job_id,))
        return rows[0] if rows else None

    def update(self, job_id: str, **fields) -> None:
        bad = fields.keys() - _UPDATABLE
        if bad:
            raise ValueError(f"can't update {bad}")
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._query(f"update jobs set {cols} where id = ?", (*fields.values(), job_id))

    def list_for(self, owner: str, limit: int = 30) -> list[dict]:
        return self._query(
            "select * from jobs where owner = ? order by created_at desc limit ?", (owner, limit)
        )

    def count_since(self, owner: str, since: float) -> int:
        # failures don't count, otherwise a yt-dlp outage eats everyone's quota
        rows = self._query(
            "select count(*) as n from jobs where owner = ? and created_at >= ? and status != 'error'",
            (owner, since),
        )
        return rows[0]["n"]

    def expired_downloads(self, before: float) -> list[dict]:
        return self._query(
            "select * from jobs where mode = 'device' and status = 'done' and finished_at < ?", (before,)
        )
