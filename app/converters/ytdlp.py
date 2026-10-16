import re
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadError, match_filter_func

from ..youtube import thumbnail_url
from .base import ConvertError, ConvertResult, Progress, Rejected

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class YtDlpConverter:
    name = "ytdlp"

    def __init__(self, quality: str, sponsorblock: bool):
        self.quality = quality
        self.sponsorblock = sponsorblock

    def convert(self, video_id: str, workdir: Path, on_progress: Progress, max_duration: int | None) -> ConvertResult:
        def hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                if total:
                    # save the last 10% for ffmpeg
                    on_progress(0.9 * d.get("downloaded_bytes", 0) / total)

        # same order the CLI uses for --sponsorblock-remove + -x
        pps = []
        if self.sponsorblock:
            pps.append({"key": "SponsorBlock", "categories": ["music_offtopic"], "when": "after_filter"})
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": self.quality})
        if self.sponsorblock:
            pps.append({"key": "ModifyChapters", "remove_sponsor_segments": ["music_offtopic"]})

        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(workdir / "audio.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [hook],
            "postprocessors": pps,
        }
        if max_duration:
            # <=? lets it through if duration is unknown
            opts["match_filter"] = match_filter_func(f"duration <=? {max_duration}")

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
        except DownloadError as e:
            raise ConvertError(_ANSI.sub("", str(e)).removeprefix("ERROR: ")) from e

        info = info or {}
        out = workdir / "audio.mp3"
        if not out.exists():
            # match_filter skips silently, so figure out why we got nothing
            dur = info.get("duration")
            if max_duration and dur and dur > max_duration:
                raise Rejected(f"too long ({dur // 60} min, limit is {max_duration // 60})")
            raise ConvertError("yt-dlp finished but produced no file")

        on_progress(0.95)
        artists = info.get("artists")
        return ConvertResult(
            path=out,
            title=info.get("title") or video_id,
            channel=info.get("channel") or info.get("uploader") or "",
            artist=", ".join(artists) if artists else info.get("artist"),
            track=info.get("track"),
            album=info.get("album"),
            thumbnails=[t for t in (info.get("thumbnail"), thumbnail_url(video_id, "maxresdefault")) if t],
        )
