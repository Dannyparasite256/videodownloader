#!/usr/bin/env bash
# Render free-tier entrypoint — fast boot, SQLite, no Redis, durable cookies from env
set -uo pipefail

export PYTHONUNBUFFERED=1
export DJANGO_SETTINGS_MODULE=config.settings
export RENDER_FREE_TIER="${RENDER_FREE_TIER:-True}"
export FORCE_SQLITE="${FORCE_SQLITE:-True}"
export CELERY_TASK_ALWAYS_EAGER="${CELERY_TASK_ALWAYS_EAGER:-True}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

echo "[render] ===== boot $(date -u +%Y-%m-%dT%H:%M:%SZ) free=${RENDER_FREE_TIER} ====="
echo "[render] PORT=${PORT:-unset} HOST=${RENDER_EXTERNAL_HOSTNAME:-}"

# Always use SQLite on free tier (ignore broken Postgres URLs left on the service)
export DATABASE_URL="sqlite:////app/db.sqlite3"

echo "[render] mkdir…"
mkdir -p \
  "${DOWNLOAD_ROOT:-/app/media/downloads}" \
  "${MEDIA_ROOT:-/app/media}" \
  /app/media/thumbnails \
  /app/media/avatars \
  /app/secrets \
  /app/logs \
  /app/staticfiles || true

# Durable YouTube cookies: set YTDLP_COOKIES_BASE64 in Render Dashboard → Environment
# (survives free sleep; file uploads alone are wiped when the free instance restarts)
if [[ -n "${YTDLP_COOKIES_BASE64:-}" ]]; then
  echo "[render] writing cookies from YTDLP_COOKIES_BASE64…"
  python - <<'PY' || echo "[render] cookie write failed (non-fatal)"
import base64, os
from pathlib import Path
raw = os.environ.get("YTDLP_COOKIES_BASE64", "").strip()
if not raw:
    raise SystemExit(0)
try:
    data = base64.b64decode(raw)
except Exception:
    data = base64.urlsafe_b64decode(raw + "==")
path = Path("/app/secrets/cookies.txt")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(data)
try:
    path.chmod(0o600)
except OSError:
    pass
print(f"[render] cookies ready ({len(data)} bytes)")
PY
else
  echo "[render] no YTDLP_COOKIES_BASE64 — YouTube will fail on cloud until set"
fi

echo "[render] migrate…"
python manage.py migrate --noinput || {
  echo "[render] migrate retry…"
  export DATABASE_URL="sqlite:////app/db.sqlite3"
  python manage.py migrate --noinput
}

# Static files are collected at Docker build — only refresh if missing (faster free cold start)
if [[ ! -f /app/staticfiles/staticfiles.json ]] && [[ ! -f /app/staticfiles/manifest.json ]]; then
  echo "[render] collectstatic (missing)…"
  python manage.py collectstatic --noinput || true
else
  echo "[render] staticfiles present — skip collectstatic"
fi

if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
  echo "[render] sync admin from env…"
  python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
u = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
p = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
e = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
if p:
    user = User.objects.filter(username=u).first()
    if user is None:
        User.objects.create_superuser(username=u, email=e or 'admin@example.com', password=p)
        print('[render] admin created', u)
    else:
        user.set_password(p)
        user.is_staff = user.is_superuser = user.is_active = True
        user.save()
        print('[render] admin password synced', u)
    try:
        from axes.models import AccessAttempt, AccessFailureLog
        AccessAttempt.objects.all().delete()
        AccessFailureLog.objects.all().delete()
    except Exception:
        pass
" || true
fi

PORT="${PORT:-8000}"
echo "[render] Daphne 0.0.0.0:${PORT}"
exec daphne -b 0.0.0.0 -p "${PORT}" --proxy-headers config.asgi:application
