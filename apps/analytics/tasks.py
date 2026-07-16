"""Analytics aggregation tasks."""
from __future__ import annotations

from collections import Counter

from celery import shared_task
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from apps.analytics.models import DailyStats
from apps.downloads.models import DownloadJob


@shared_task(name="apps.analytics.tasks.aggregate_daily_stats")
def aggregate_daily_stats() -> dict:
    """Aggregate yesterday's global stats."""
    yesterday = timezone.now().date() - timezone.timedelta(days=1)
    qs = DownloadJob.objects.filter(created_at__date=yesterday)

    started = qs.count()
    completed = qs.filter(status=DownloadJob.Status.COMPLETED).count()
    failed = qs.filter(status=DownloadJob.Status.FAILED).count()
    bytes_dl = (
        qs.filter(status=DownloadJob.Status.COMPLETED).aggregate(s=Sum("file_size"))["s"]
        or 0
    )
    avg_speed = qs.filter(speed_bps__isnull=False).aggregate(a=Avg("speed_bps"))["a"]

    platforms = Counter(qs.values_list("platform", flat=True))
    formats = Counter(
        qs.filter(status=DownloadJob.Status.COMPLETED).values_list(
            "output_format", flat=True
        )
    )

    DailyStats.objects.update_or_create(
        user=None,
        date=yesterday,
        defaults={
            "downloads_started": started,
            "downloads_completed": completed,
            "downloads_failed": failed,
            "bytes_downloaded": bytes_dl,
            "avg_speed_bps": avg_speed,
            "platform_breakdown": dict(platforms),
            "format_breakdown": dict(formats),
        },
    )
    return {"date": str(yesterday), "started": started, "completed": completed}
