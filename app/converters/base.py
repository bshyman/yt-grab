from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

Progress = Callable[[float], None]


class ConvertError(Exception):
    pass


class Rejected(ConvertError):
    # we refused it (too long etc), so don't bother trying the next converter
    pass


@dataclass
class ConvertResult:
    path: Path
    title: str
    channel: str = ""
    artist: str | None = None
    track: str | None = None
    album: str | None = None
    thumbnails: list[str] = field(default_factory=list)


class Converter(Protocol):
    name: str

    def convert(
        self, video_id: str, workdir: Path, on_progress: Progress, max_duration: int | None
    ) -> ConvertResult: ...
