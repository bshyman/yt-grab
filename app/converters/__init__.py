import logging
from pathlib import Path

from ..config import Settings
from .base import ConvertError, ConvertResult, Converter, Progress, Rejected
from .rapidapi import RapidApiConverter
from .ytdlp import YtDlpConverter

log = logging.getLogger(__name__)

__all__ = ["ConvertError", "ConvertResult", "Converter", "Rejected", "build_chain", "convert"]


def build_chain(settings: Settings) -> list[Converter]:
    chain: list[Converter] = []
    for name in settings.converters:
        if name == "ytdlp":
            chain.append(YtDlpConverter(settings.audio_quality, settings.sponsorblock))
        elif name == "rapidapi":
            # no key = no fallback, not an error
            if settings.rapidapi_key:
                chain.append(RapidApiConverter(settings.rapidapi_key, settings.rapidapi_host))
        else:
            raise ValueError(f"unknown converter {name!r}")
    return chain


def convert(
    chain: list[Converter], video_id: str, workdir: Path, on_progress: Progress, max_duration: int | None
) -> ConvertResult:
    if not chain:
        raise ConvertError("no converters configured")
    errors = []
    for c in chain:
        try:
            return c.convert(video_id, workdir, on_progress, max_duration)
        except Rejected:
            raise
        except Exception as e:
            log.warning("%s failed for %s: %s", c.name, video_id, e)
            errors.append(f"{c.name}: {e}")
            on_progress(0.0)
    raise ConvertError("; ".join(errors))
