import subprocess
from pathlib import Path

import httpx

from .meta import TrackMeta


def _fetch_cover(urls: list[str], dest: Path) -> bool:
    for url in urls:
        try:
            r = httpx.get(url, timeout=10, follow_redirects=True)
        except httpx.HTTPError:
            continue
        if r.status_code == 200 and r.content:
            dest.write_bytes(r.content)
            return True
    return False


def tag_mp3(src: Path, dst: Path, meta: TrackMeta, cover_urls: list[str]) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]

    cover = src.with_name("cover.img")
    if _fetch_cover(cover_urls, cover):
        cmd += [
            "-i", str(cover),
            "-map", "0:a", "-map", "1:v",
            # thumbnails are 16:9, album art wants square
            "-c:v", "mjpeg", "-vf", "crop='min(iw,ih)':'min(iw,ih)'",
            "-disposition:v", "attached_pic",
            "-metadata:s:v", "title=Album cover",
            "-metadata:s:v", "comment=Cover (front)",
        ]
    else:
        cmd += ["-map", "0:a"]

    cmd += [
        "-c:a", "copy",
        "-map_metadata", "-1",
        "-id3v2_version", "3",
        "-metadata", f"title={meta.title}",
        "-metadata", f"artist={meta.artist}",
        "-metadata", f"album_artist={meta.artist}",
        "-metadata", f"album={meta.album}",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg tagging failed: {proc.stderr.strip()[-300:]}")
