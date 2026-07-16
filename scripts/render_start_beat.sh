#!/usr/bin/env bash
# Render.com Celery beat (optional scheduled tasks)
set -euo pipefail

echo "[render] starting Celery beat…"
exec celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
