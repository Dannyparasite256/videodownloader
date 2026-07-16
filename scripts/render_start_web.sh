#!/usr/bin/env bash
# Render.com web process entrypoint
set -euo pipefail

echo "[render] migrate…"
python manage.py migrate --noinput

echo "[render] collectstatic…"
python manage.py collectstatic --noinput

# Optional: create empty dirs for downloads
mkdir -p "${DOWNLOAD_ROOT:-/app/media/downloads}" "${MEDIA_ROOT:-/app/media}"

PORT="${PORT:-8000}"
echo "[render] starting Daphne on 0.0.0.0:${PORT}"
exec daphne -b 0.0.0.0 -p "${PORT}" config.asgi:application
