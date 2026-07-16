#!/usr/bin/env bash
# Render.com Celery worker entrypoint
set -euo pipefail

echo "[render] starting Celery worker…"
exec celery -A config worker \
  -l info \
  -Q celery,downloads,maintenance,analytics,notifications \
  -c "${CELERY_CONCURRENCY:-1}" \
  --max-tasks-per-child=50
