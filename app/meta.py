import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TrackMeta:
    artist: str
    title: str
    album: str


# (Official Video), [Lyric Video], (HD), (Visualizer)...
_NOISE = re.compile(
    r"\s*[\(\[][^\)\]]*\b(?:official|video|audio|lyrics?|visuali[sz]er|hd|hq|4k|mv)\b[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
_SPLIT = re.compile(r"\s+[-–—]\s+")
_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def clean_channel(channel: str) -> str:
    c = re.sub(r"\s*-\s*Topic$", "", channel or "")
    c = re.sub(r"\s*VEVO$", "", c, flags=re.IGNORECASE)
    return c.strip()


def parse_title(
    title: str,
    channel: str = "",
    artist: str | None = None,
    track: str | None = None,
    album: str | None = None,
) -> TrackMeta:
    # YouTube Music uploads come with real metadata, trust that over guessing
    if artist and track:
        return TrackMeta(artist, track, album or track)

    clean = _NOISE.sub("", title or "").strip()
    parts = _SPLIT.split(clean, maxsplit=1)
    if len(parts) == 2 and all(p.strip() for p in parts):
        a, t = parts
    else:
        a, t = clean_channel(channel), clean

    t = t.strip().strip('"“”').strip() or "Untitled"
    a = a.strip() or "Unknown Artist"
    # singles convention: album = track title
    return TrackMeta(a, t, album or t)


def safe_name(s: str, max_len: int = 120) -> str:
    s = _BAD_CHARS.sub("", s or "").strip().strip(".").strip()
    return s[:max_len].rstrip() or "untitled"
