#!/usr/bin/env bash
# Render.com web process entrypoint
set -euo pipefail

echo "[render] migrate…"
python manage.py migrate --noinput

echo "[render] collectstatic…"
python manage.py collectstatic --noinput

# Create empty dirs for downloads / media (ephemeral on Free tier)
mkdir -p "${DOWNLOAD_ROOT:-/opt/render/project/src/media/downloads}" \
         "${MEDIA_ROOT:-/opt/render/project/src/media}"

# Free web services have no Shell — create admin from env if set (idempotent)
if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
  echo "[render] ensuring superuser exists…"
  python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
u = '${DJANGO_SUPERUSER_USERNAME}'
if not User.objects.filter(username=u).exists():
    User.objects.create_superuser(
        username=u,
        email='${DJANGO_SUPERUSER_EMAIL:-admin@example.com}',
        password='${DJANGO_SUPERUSER_PASSWORD}',
    )
    print('[render] superuser created:', u)
else:
    print('[render] superuser already exists:', u)
" || echo "[render] superuser step skipped (non-fatal)"
fi

PORT="${PORT:-8000}"
echo "[render] starting Daphne on 0.0.0.0:${PORT}"
exec daphne -b 0.0.0.0 -p "${PORT}" config.asgi:application
