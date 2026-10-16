import os
from dataclasses import dataclass
from pathlib import Path


def _bool(raw: str | None, default: bool) -> bool:
    return default if raw is None else raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    music_dir: Path
    library_subdir: str
    admin_password: str
    daily_limit: int
    max_duration_min: int
    max_concurrent: int
    file_ttl_hours: int
    audio_quality: str
    converters: tuple[str, ...]
    sponsorblock: bool
    rapidapi_key: str
    rapidapi_host: str
    plex_url: str
    plex_token: str
    plex_section_id: str
    plex_music_path: str

    @property
    def library_enabled(self) -> bool:
        return self.music_dir.is_dir()


def load_settings() -> Settings:
    env = os.environ.get
    return Settings(
        data_dir=Path(env("DATA_DIR", "/data")),
        music_dir=Path(env("MUSIC_DIR", "/music")),
        library_subdir=env("LIBRARY_SUBDIR", "YouTube"),
        admin_password=env("ADMIN_PASSWORD", ""),
        daily_limit=int(env("DAILY_LIMIT", "20")),
        max_duration_min=int(env("MAX_DURATION_MIN", "20")),
        max_concurrent=int(env("MAX_CONCURRENT", "2")),
        file_ttl_hours=int(env("FILE_TTL_HOURS", "24")),
        audio_quality=env("AUDIO_QUALITY", "320"),
        converters=tuple(c.strip() for c in env("CONVERTERS", "ytdlp,rapidapi").split(",") if c.strip()),
        sponsorblock=_bool(env("SPONSORBLOCK"), True),
        rapidapi_key=env("RAPIDAPI_KEY", ""),
        rapidapi_host=env("RAPIDAPI_HOST", "youtube-mp36.p.rapidapi.com"),
        plex_url=env("PLEX_URL", "").rstrip("/"),
        plex_token=env("PLEX_TOKEN", ""),
        plex_section_id=env("PLEX_SECTION_ID", ""),
        plex_music_path=env("PLEX_MUSIC_PATH", ""),
    )
