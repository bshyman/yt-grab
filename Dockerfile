FROM python:3.12-slim

# yt-dlp needs a JS runtime to solve YouTube's player challenges
COPY --from=denoland/deno:bin-2.9.7 /deno /usr/local/bin/deno
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
# deliberately not using uv.lock here, the weekly rebuild exists to pull the newest yt-dlp
RUN uv pip install --system --no-cache -r pyproject.toml

COPY app ./app
COPY docker/entrypoint.sh /entrypoint.sh

# HOME matters: app runs as nobody, yt-dlp + deno need somewhere writable for caches
ENV DATA_DIR=/data \
    MUSIC_DIR=/music \
    HOME=/data \
    XDG_CACHE_HOME=/data/.cache \
    PYTHONUNBUFFERED=1

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
ENTRYPOINT ["/entrypoint.sh"]
