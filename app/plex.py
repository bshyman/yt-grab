import logging
from pathlib import Path, PurePosixPath

import httpx

from .config import Settings

log = logging.getLogger(__name__)


def refresh(settings: Settings, folder: Path) -> None:
    if not (settings.plex_url and settings.plex_token and settings.plex_section_id):
        return

    params = {"X-Plex-Token": settings.plex_token}
    # partial scan of just the new folder, so we're not rescanning the whole library every time.
    # needs the path as *Plex's* container sees it, not ours
    if settings.plex_music_path:
        rel = folder.relative_to(settings.music_dir)
        params["path"] = str(PurePosixPath(settings.plex_music_path) / rel)

    url = f"{settings.plex_url}/library/sections/{settings.plex_section_id}/refresh"
    try:
        httpx.get(url, params=params, timeout=10).raise_for_status()
    except httpx.HTTPError as e:
        # file's already in place, a failed scan isn't worth failing the job over
        log.warning("plex refresh failed: %s", e)
