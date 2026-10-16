#!/bin/sh
set -e

# unRAID convention: nobody:users with an open umask, so files on the share stay editable over SMB
umask "${UMASK:-000}"

set -- uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8000

if [ "$(id -u)" = "0" ]; then
  PUID="${PUID:-99}"
  PGID="${PGID:-100}"
  mkdir -p "$DATA_DIR"
  chown "$PUID:$PGID" "$DATA_DIR"
  exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
fi

exec "$@"
