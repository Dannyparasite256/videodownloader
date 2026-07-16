"""Maintenance Celery tasks for downloads."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.downloads.tasks.cleanup_expired_downloads")
def cleanup_expired_downloads() -> dict:
    """Remove files for expired completed downloads."""
    from apps.downloads.models import DownloadJob

    now = timezone.now()
    expired = DownloadJob.objects.filter(
        status=DownloadJob.Status.COMPLETED,
        expires_at__lte=now,
        is_deleted=False,
    )
    removed = 0
    for job in expired.iterator():
        if job.file_path:
            p = Path(job.file_path)
            if p.exists():
                try:
                    p.unlink()
                    removed += 1
                except OSError as exc:
                    logger.warning("Could not delete %s: %s", p, exc)
        job_dir = Path(settings.DOWNLOAD_ROOT) / str(job.id)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        job.status = DownloadJob.Status.EXPIRED
        job.file_path = ""
        job.save(update_fields=["status", "file_path", "updated_at"])
    return {"expired": expired.count(), "files_removed": removed}


@shared_task(name="apps.downloads.tasks.cleanup_temp_files")
def cleanup_temp_files() -> dict:
    """Remove orphaned .part / temp files older than 6 hours."""
    root = Path(settings.DOWNLOAD_ROOT)
    if not root.exists():
        return {"removed": 0}
    cutoff = timezone.now().timestamp() - 6 * 3600
    removed = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".part", ".ytdl", ".temp"} or path.name.endswith(".part"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                pass
    return {"removed": removed}


@shared_task(name="apps.downloads.tasks.check_storage_health")
def check_storage_health() -> dict:
    """Report free disk space for monitoring."""
    root = Path(settings.DOWNLOAD_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(root)
    data = {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "free_percent": round((usage.free / usage.total) * 100, 1) if usage.total else 0,
    }
    if data["free_percent"] < 10:
        logger.warning("Low disk space: %s%% free", data["free_percent"])
    return data
