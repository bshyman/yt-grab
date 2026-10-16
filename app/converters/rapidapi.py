import time
from pathlib import Path

import httpx

from ..youtube import thumbnail_url
from .base import ConvertError, ConvertResult, Progress, Rejected


class RapidApiConverter:
    """youtube-mp36 (ytjar). Other providers have different shapes, swap this out if you switch."""

    name = "rapidapi"

    def __init__(self, key: str, host: str):
        self.key = key
        self.host = host

    def convert(self, video_id: str, workdir: Path, on_progress: Progress, max_duration: int | None) -> ConvertResult:
        headers = {"x-rapidapi-key": self.key, "x-rapidapi-host": self.host}
        out = workdir / "audio.mp3"

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            # they convert async, poll until it's ready
            for _ in range(60):
                r = client.get(f"https://{self.host}/dl", params={"id": video_id}, headers=headers)
                if r.status_code == 429:
                    raise ConvertError("rapidapi quota exhausted")
                r.raise_for_status()
                data = r.json()
                status = data.get("status")
                if status == "ok":
                    break
                if status != "processing":
                    raise ConvertError(f"rapidapi: {data.get('msg') or status}")
                time.sleep(2)
            else:
                raise ConvertError("rapidapi: timed out waiting for conversion")

            dur = int(data.get("duration") or 0)
            if max_duration and dur > max_duration:
                raise Rejected(f"too long ({dur // 60} min, limit is {max_duration // 60})")

            with client.stream("GET", data["link"]) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or 0)
                done = 0
                with out.open("wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            on_progress(0.9 * done / total)

        return ConvertResult(
            path=out,
            title=data.get("title") or video_id,
            thumbnails=[thumbnail_url(video_id, "maxresdefault"), thumbnail_url(video_id, "hqdefault")],
        )
