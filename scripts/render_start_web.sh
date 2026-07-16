#!/usr/bin/env bash
# Render.com web process entrypoint (free-tier friendly)
set -euo pipefail

export PYTHONUNBUFFERED=1

echo "[render] mkdir media/secrets…"
mkdir -p \
  "${DOWNLOAD_ROOT:-/app/media/downloads}" \
  "${MEDIA_ROOT:-/app/media}" \
  /app/media/thumbnails \
  /app/media/avatars \
  /app/secrets \
  /app/logs || true

echo "[render] migrate…"
python manage.py migrate --noinput

echo "[render] collectstatic…"
python manage.py collectstatic --noinput

# Free web services have no Shell — create admin from env if set (idempotent)
if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
  echo "[render] ensuring superuser exists…"
  python manage.py shell -c "import os; from django.contrib.auth import get_user_model; U=get_user_model(); u=os.environ.get('DJANGO_SUPERUSER_USERNAME','admin'); p=os.environ.get('DJANGO_SUPERUSER_PASSWORD',''); e=os.environ.get('DJANGO_SUPERUSER_EMAIL','admin@example.com');
(print('[render] superuser created', u) if p and not U.objects.filter(username=u).exists() and U.objects.create_superuser(username=u, email=e, password=p) is None else print('[render] superuser ok', u))" \
    || echo "[render] superuser step skipped (non-fatal)"
fi

PORT="${PORT:-8000}"
echo "[render] starting Daphne on 0.0.0.0:${PORT}"
exec daphne -b 0.0.0.0 -p "${PORT}" --proxy-headers config.asgi:application
