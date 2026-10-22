# yt-grab

Search YouTube or paste a link, get a tagged MP3 (artist/title/album + square cover art).

- **Admin** (password): "Add to Plex" drops it into `/music/YouTube/Artist/Album/Track.mp3` and kicks a partial Plex scan.
- **Friends**: "Download" gives them the file. Kept 24h, then swept. Daily limit + max video length apply.

yt-dlp does the work. RapidAPI (youtube-mp36) is an optional fallback for when YouTube breaks yt-dlp.

## Dev

```sh
uv run pytest
DATA_DIR=./data MUSIC_DIR=./music ADMIN_PASSWORD=dev uv run uvicorn --factory app.main:create_app --reload
```

Needs `ffmpeg` on PATH. Install `deno` too if you hit YouTube JS-challenge errors.

## Deploy

1. Push to `github.com/bshyman/yt-grab`. Actions runs tests, builds `linux/amd64`, pushes `ghcr.io/bshyman/yt-grab:latest`. Rebuilds every Monday to pick up new yt-dlp.
2. **Make the package public** (GitHub → Packages → yt-grab → settings). A private image means `docker login` on unRAID, and that login lives in RAM, so it's gone after a reboot.
3. On .158: copy `unraid/yt-grab.xml` to `/boot/config/plugins/dockerMan/templates-user/my-yt-grab.xml`, then Docker → Add Container → pick `yt-grab`.
4. Fill in the admin password + Plex bits (below). Check the music share path, the template points at the PICHU share (`/mnt/remotes/PICHU_Library/Music`, mounted `rw,slave` since it's a remote mount).
5. In the template, turn on **Use Tailscale**, hostname `yt-grab`, Serve on. Then share the `yt-grab` machine with friends from the Tailscale admin console (Machines → ⋯ → Share).
6. Install **CA Auto Update Applications** so the weekly images actually get pulled.

### Plex

- `PLEX_TOKEN`: [finding your token](https://support.plex.tv/articles/204059436)
- `PLEX_SECTION_ID`: `curl "http://192.168.1.158:32400/library/sections?X-Plex-Token=TOKEN"`, use the `key` of the music library
- `PLEX_MUSIC_PATH`: the music share *as Plex's container sees it* (check binhex-plexpass's path mappings, for the PICHU share that's `/pichu-share/Music`). Leave blank and it rescans the whole section instead.

## Config

| Var | Default | |
|---|---|---|
| `ADMIN_PASSWORD` | | required for admin |
| `APP_NAME` | `yt-grab` | page header + tab title |
| `DAILY_LIMIT` | `20` | per friend, failed jobs don't count, 0 = off |
| `MAX_DURATION_MIN` | `20` | friends only, 0 = off |
| `AUDIO_QUALITY` | `320` | MP3 kbps |
| `SPONSORBLOCK` | `true` | strips `music_offtopic` segments |
| `CONVERTERS` | `ytdlp,rapidapi` | tried in order |
| `RAPIDAPI_KEY` | | no key = no fallback |
| `RAPIDAPI_HOST` | `youtube-mp36.p.rapidapi.com` | other providers need a new converter |
| `LIBRARY_SUBDIR` | `YouTube` | blank = straight into `/music` |
| `FILE_TTL_HOURS` | `24` | friends' downloads |
| `MAX_CONCURRENT` | `2` | parallel jobs |
| `PUID` / `PGID` / `UMASK` | `99` / `100` / `000` | unRAID defaults |

## Notes

- Who's who comes from Tailscale Serve's `Tailscale-User-Login` header. Over the LAN port it falls back to IP, and that's spoofable. Fine for rate limiting, don't use it for anything that matters.
- Single videos only for now. Playlist links get a clear error.
