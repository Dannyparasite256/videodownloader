#!/usr/bin/env bash
# Render.com web process entrypoint (free-tier friendly, fail-soft)
set -uo pipefail

export PYTHONUNBUFFERED=1
export DJANGO_SETTINGS_MODULE=config.settings

echo "[render] ===== boot $(date -u +%Y-%m-%dT%H:%M:%SZ) ====="
echo "[render] PORT=${PORT:-unset}"
echo "[render] DATABASE_URL set? $([ -n "${DATABASE_URL:-}" ] && echo yes || echo no)"
echo "[render] RENDER=${RENDER:-} HOSTNAME=${RENDER_EXTERNAL_HOSTNAME:-}"

# Free tier: if DATABASE_URL is missing or still points at a dead Postgres, use SQLite
if [[ -z "${DATABASE_URL:-}" ]] || [[ "${DATABASE_URL}" == postgres* ]] || [[ "${DATABASE_URL}" == *"dpg-"* ]]; then
  echo "[render] forcing SQLite (free-tier safe)"
  export DATABASE_URL="sqlite:////app/db.sqlite3"
fi

# Never block boot on Redis for free tier
export CELERY_TASK_ALWAYS_EAGER="${CELERY_TASK_ALWAYS_EAGER:-True}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

echo "[render] mkdir…"
mkdir -p \
  "${DOWNLOAD_ROOT:-/app/media/downloads}" \
  "${MEDIA_ROOT:-/app/media}" \
  /app/media/thumbnails \
  /app/media/avatars \
  /app/secrets \
  /app/logs \
  /app/staticfiles || true

echo "[render] migrate…"
if ! python manage.py migrate --noinput; then
  echo "[render] migrate failed — retrying with SQLite"
  export DATABASE_URL="sqlite:////app/db.sqlite3"
  python manage.py migrate --noinput
fi

echo "[render] collectstatic…"
python manage.py collectstatic --noinput || echo "[render] collectstatic failed (non-fatal)"

if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
  echo "[render] ensuring superuser (password synced from env)…"
  python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
u = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
p = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
e = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
if not p:
    print('[render] no superuser password env')
else:
    user = User.objects.filter(username=u).first()
    if user is None:
        User.objects.create_superuser(username=u, email=e or 'admin@example.com', password=p)
        print('[render] superuser created', u)
    else:
        user.set_password(p)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if e and not user.email:
            user.email = e
        user.save()
        print('[render] superuser password reset', u)
    # Clear django-axes lockouts so failed tries do not block admin after redeploy
    try:
        from axes.models import AccessAttempt, AccessFailureLog
        AccessAttempt.objects.all().delete()
        AccessFailureLog.objects.all().delete()
        print('[render] cleared login lockouts')
    except Exception as exc:
        print('[render] axes clear skipped', exc)
" || echo "[render] superuser step skipped"
fi

PORT="${PORT:-8000}"
echo "[render] starting Daphne on 0.0.0.0:${PORT}"
exec daphne -b 0.0.0.0 -p "${PORT}" --proxy-headers config.asgi:application
