import re
from urllib.parse import parse_qs, urlparse

import httpx
import yt_dlp

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_HOSTS = {"youtube.com", "music.youtube.com", "youtube-nocookie.com", "youtu.be"}


def _youtube_url(text: str):
    text = text.strip()
    if not text or any(c.isspace() for c in text):
        return None
    u = urlparse(text if "://" in text else f"https://{text}")
    host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    return (host, u) if host in _HOSTS else None


def is_youtube_url(text: str) -> bool:
    return _youtube_url(text) is not None


def extract_video_id(text: str) -> str | None:
    hit = _youtube_url(text)
    if not hit:
        return None
    host, u = hit
    parts = [p for p in u.path.split("/") if p]
    if host == "youtu.be":
        cand = parts[0] if parts else ""
    elif u.path == "/watch":
        cand = parse_qs(u.query).get("v", [""])[0]
    elif len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
        cand = parts[1]
    else:
        cand = ""
    return cand if VIDEO_ID.fullmatch(cand) else None


def thumbnail_url(video_id: str, size: str = "mqdefault") -> str:
    return f"https://i.ytimg.com/vi/{video_id}/{size}.jpg"


def search(query: str, limit: int = 10) -> list[dict]:
    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

    results = []
    for e in info.get("entries") or []:
        vid = (e or {}).get("id") or ""
        # search can return channels/playlists too, only want videos
        if not VIDEO_ID.fullmatch(vid):
            continue
        results.append({
            "id": vid,
            "title": e.get("title") or vid,
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration": e.get("duration"),
            "thumbnail": thumbnail_url(vid),
        })
    return results


async def lookup(video_id: str) -> dict:
    # oEmbed is way faster than spinning up yt-dlp just for a title
    result = {"id": video_id, "title": video_id, "channel": "", "duration": None, "thumbnail": thumbnail_url(video_id)}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            )
        if r.status_code == 200:
            d = r.json()
            result |= {"title": d.get("title") or video_id, "channel": d.get("author_name") or ""}
    except httpx.HTTPError:
        pass
    return result
