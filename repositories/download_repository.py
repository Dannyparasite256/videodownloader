"""Repository pattern for DownloadJob data access."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from django.db.models import Q, QuerySet, Sum
from django.utils import timezone

from apps.downloads.models import DownloadJob, DuplicateFingerprint


class DownloadRepository:
    """Encapsulates all DownloadJob queries and mutations."""

    model = DownloadJob

    def get_by_id(self, download_id: str | UUID) -> Optional[DownloadJob]:
        try:
            return self.model.objects.select_related("user", "folder").get(
                id=download_id, is_deleted=False
            )
        except self.model.DoesNotExist:
            return None

    def get_for_user(
        self,
        user,
        *,
        session_key: str = "",
        include_deleted: bool = False,
    ) -> QuerySet[DownloadJob]:
        qs = self.model.objects.all()
        if not include_deleted:
            qs = qs.filter(is_deleted=False)
        if user and user.is_authenticated:
            return qs.filter(user=user)
        if session_key:
            return qs.filter(session_key=session_key, user__isnull=True)
        return qs.none()

    def list_history(
        self,
        user,
        *,
        session_key: str = "",
        search: str = "",
        status: str = "",
        platform: str = "",
        favorite: Optional[bool] = None,
        ordering: str = "-created_at",
    ) -> QuerySet[DownloadJob]:
        qs = self.get_for_user(user, session_key=session_key)
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(uploader__icontains=search)
                | Q(url__icontains=search)
                | Q(platform__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        if platform:
            qs = qs.filter(platform=platform)
        if favorite is not None:
            qs = qs.filter(is_favorite=favorite)
        allowed = {
            "created_at",
            "-created_at",
            "title",
            "-title",
            "status",
            "-status",
            "file_size",
            "-file_size",
        }
        if ordering not in allowed:
            ordering = "-created_at"
        return qs.order_by(ordering)

    def create(self, **kwargs: Any) -> DownloadJob:
        return self.model.objects.create(**kwargs)

    def update(self, job: DownloadJob, **fields: Any) -> DownloadJob:
        for k, v in fields.items():
            setattr(job, k, v)
        job.save(update_fields=list(fields.keys()) + ["updated_at"])
        return job

    def soft_delete(self, job: DownloadJob) -> None:
        job.is_deleted = True
        job.save(update_fields=["is_deleted", "updated_at"])

    def restore(self, job: DownloadJob) -> None:
        job.is_deleted = False
        job.save(update_fields=["is_deleted", "updated_at"])

    def active_count(self, user=None) -> int:
        qs = self.model.objects.filter(
            status__in=[
                DownloadJob.Status.QUEUED,
                DownloadJob.Status.DOWNLOADING,
                DownloadJob.Status.PROCESSING,
                DownloadJob.Status.MERGING,
                DownloadJob.Status.CONVERTING,
            ],
            is_deleted=False,
        )
        if user and user.is_authenticated:
            qs = qs.filter(user=user)
        return qs.count()

    def find_duplicate(
        self,
        user,
        platform: str,
        video_id: str,
        quality: str,
        mode: str,
    ) -> Optional[DownloadJob]:
        if not video_id:
            return None
        qs = DuplicateFingerprint.objects.filter(
            platform=platform,
            video_id=video_id,
            quality=quality,
            mode=mode,
        )
        if user and user.is_authenticated:
            qs = qs.filter(user=user)
        else:
            qs = qs.filter(user__isnull=True)
        fp = qs.select_related("download").first()
        if fp and not fp.download.is_deleted and fp.download.status == DownloadJob.Status.COMPLETED:
            return fp.download
        return None

    def register_fingerprint(self, job: DownloadJob) -> None:
        if not job.video_id:
            return
        DuplicateFingerprint.objects.update_or_create(
            user=job.user,
            platform=job.platform,
            video_id=job.video_id,
            quality=job.quality,
            mode=job.mode,
            defaults={"download": job},
        )

    def stats_for_user(self, user, session_key: str = "") -> dict[str, Any]:
        qs = self.get_for_user(user, session_key=session_key)
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week = today - timezone.timedelta(days=today.weekday())
        month = today.replace(day=1)

        def count_since(dt):
            return qs.filter(created_at__gte=dt).count()

        completed = qs.filter(status=DownloadJob.Status.COMPLETED)
        failed = qs.filter(status=DownloadJob.Status.FAILED)
        total = qs.count()
        success = completed.count()
        storage = completed.aggregate(s=Sum("file_size"))["s"] or 0

        platform_row = (
            completed.values("platform")
            .annotate(c=models_count())
            .order_by("-c")
            .first()
        )
        format_row = (
            completed.values("output_format")
            .annotate(c=models_count())
            .order_by("-c")
            .first()
        )

        return {
            "total": total,
            "today": count_since(today),
            "week": count_since(week),
            "month": count_since(month),
            "completed": success,
            "failed": failed.count(),
            "success_rate": round((success / total) * 100, 1) if total else 0,
            "storage_used": storage,
            "favorite_platform": (platform_row or {}).get("platform") or "—",
            "top_format": (format_row or {}).get("output_format") or "—",
            "active": qs.filter(
                status__in=[
                    DownloadJob.Status.DOWNLOADING,
                    DownloadJob.Status.QUEUED,
                    DownloadJob.Status.PROCESSING,
                ]
            ).count(),
        }


def models_count():
    from django.db.models import Count

    return Count("id")
