"""Celery tasks for the download engine."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="apps.downloader.tasks.process_download",
    max_retries=0,  # retries handled in service layer
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=60 * 60 * 4,
    soft_time_limit=60 * 60 * 3,
)
def process_download(self, job_id: str) -> dict:
    """Execute a download job on a worker."""
    from services.download_service import DownloadService

    logger.info("Worker starting job %s (task %s)", job_id, self.request.id)
    service = DownloadService()
    service.execute_download(job_id)
    return {"job_id": job_id, "task_id": self.request.id}


@shared_task(name="apps.downloader.tasks.fetch_metadata_async")
def fetch_metadata_async(url: str) -> dict:
    """Background metadata fetch (optional prefetch)."""
    from services.download_service import DownloadService, DownloadServiceError

    try:
        return DownloadService().fetch_metadata(url)
    except DownloadServiceError as exc:
        return {"error": str(exc), "code": exc.code}
