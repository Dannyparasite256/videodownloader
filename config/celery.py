"""Celery application configuration."""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("video_downloader")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "cleanup-expired-downloads": {
        "task": "apps.downloads.tasks.cleanup_expired_downloads",
        "schedule": crontab(hour=3, minute=0),
    },
    "cleanup-temp-files": {
        "task": "apps.downloads.tasks.cleanup_temp_files",
        "schedule": crontab(minute="*/30"),
    },
    "aggregate-daily-stats": {
        "task": "apps.analytics.tasks.aggregate_daily_stats",
        "schedule": crontab(hour=0, minute=15),
    },
    "health-check-storage": {
        "task": "apps.downloads.tasks.check_storage_health",
        "schedule": crontab(minute="*/15"),
    },
}

app.conf.task_routes = {
    "apps.downloader.tasks.*": {"queue": "downloads"},
    "apps.downloads.tasks.*": {"queue": "maintenance"},
    "apps.analytics.tasks.*": {"queue": "analytics"},
    "apps.notifications.tasks.*": {"queue": "notifications"},
}


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> str:
    """Debug task for verifying Celery worker connectivity."""
    return f"Request: {self.request!r}"
