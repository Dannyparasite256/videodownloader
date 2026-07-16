"""User dashboard with stats and charts."""
from __future__ import annotations

import json
from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.downloads.models import DownloadJob
from repositories.download_repository import DownloadRepository
from utils.format_utils import format_bytes


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    repo = DownloadRepository()
    stats = repo.stats_for_user(request.user)

    # Last 14 days series
    since = timezone.now() - timezone.timedelta(days=14)
    daily = (
        DownloadJob.objects.filter(user=request.user, created_at__gte=since, is_deleted=False)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    labels = [str(row["day"]) for row in daily]
    values = [row["count"] for row in daily]

    platforms = (
        DownloadJob.objects.filter(
            user=request.user,
            status=DownloadJob.Status.COMPLETED,
            is_deleted=False,
        )
        .values("platform")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )
    platform_labels = [p["platform"] or "other" for p in platforms]
    platform_values = [p["count"] for p in platforms]

    recent = (
        DownloadJob.objects.filter(user=request.user, is_deleted=False)
        .order_by("-created_at")[:8]
    )
    active = DownloadJob.objects.filter(
        user=request.user,
        status__in=[
            DownloadJob.Status.DOWNLOADING,
            DownloadJob.Status.QUEUED,
            DownloadJob.Status.PROCESSING,
        ],
        is_deleted=False,
    ).order_by("-created_at")[:10]

    return render(
        request,
        "dashboard/index.html",
        {
            "stats": stats,
            "storage_used_display": format_bytes(stats["storage_used"]),
            "storage_quota_display": format_bytes(
                request.user.storage_quota_mb * 1024 * 1024
            ),
            "storage_percent": request.user.storage_usage_percent,
            "chart_daily_labels": json.dumps(labels),
            "chart_daily_values": json.dumps(values),
            "chart_platform_labels": json.dumps(platform_labels),
            "chart_platform_values": json.dumps(platform_values),
            "recent": recent,
            "active": active,
        },
    )
