#!/bin/sh
# Render (and some Docker hosts) mount the data volume as root. Fix ownership, then drop to the unprivileged user.
set -e
mkdir -p "${WORK_DIR:-/app/data/work}"
chown -R app:app /app/data 2>/dev/null || true
exec setpriv --reuid=10001 --regid=10001 --init-groups \
  uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
