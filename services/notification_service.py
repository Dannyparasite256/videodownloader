"""Notification creation and delivery helpers."""
from __future__ import annotations

import logging
from typing import Optional

from apps.downloads.models import DownloadJob

logger = logging.getLogger(__name__)


class NotificationService:
    def notify_download_complete(self, job: DownloadJob) -> None:
        if not job.user_id:
            return
        from apps.notifications.models import Notification

        Notification.objects.create(
            user_id=job.user_id,
            kind=Notification.Kind.DOWNLOAD_COMPLETE,
            title="Download complete",
            message=f"“{job.title or 'Your file'}” is ready.",
            link=f"/history/{job.id}/",
            metadata={"download_id": str(job.id)},
        )

    def notify_download_failed(self, job: DownloadJob, error: str = "") -> None:
        if not job.user_id:
            return
        from apps.notifications.models import Notification

        Notification.objects.create(
            user_id=job.user_id,
            kind=Notification.Kind.DOWNLOAD_FAILED,
            title="Download failed",
            message=error or f"“{job.title or 'Download'}” failed.",
            link=f"/history/{job.id}/",
            metadata={"download_id": str(job.id)},
        )

    def notify(self, user_id, kind: str, title: str, message: str, **kwargs) -> Optional[object]:
        from apps.notifications.models import Notification

        return Notification.objects.create(
            user_id=user_id,
            kind=kind,
            title=title,
            message=message,
            **kwargs,
        )
