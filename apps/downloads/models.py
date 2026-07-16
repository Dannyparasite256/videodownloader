"""Download job, history, folders, tags, and queue models."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from django.conf import settings
from django.db import models
from django.utils import timezone


class Folder(models.Model):
    """User-organized download folders."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="folders",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=128)
    color = models.CharField(max_length=7, default="#6366f1")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["user", "name", "parent"]]

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=64)
    color = models.CharField(max_length=7, default="#8b5cf6")

    class Meta:
        ordering = ["name"]
        unique_together = [["user", "name"]]

    def __str__(self) -> str:
        return self.name


class DownloadJob(models.Model):
    """
    Core download job entity.

    Tracks full lifecycle: metadata fetch → queue → download → convert → complete.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FETCHING_META = "fetching_meta", "Fetching Metadata"
        QUEUED = "queued", "Queued"
        DOWNLOADING = "downloading", "Downloading"
        PROCESSING = "processing", "Processing"
        MERGING = "merging", "Merging"
        CONVERTING = "converting", "Converting"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Mode(models.TextChoices):
        VIDEO_AUDIO = "video_audio", "Video + Audio"
        VIDEO_ONLY = "video_only", "Video Only"
        AUDIO_ONLY = "audio_only", "Audio Only"
        SUBTITLES = "subtitles", "Subtitles"
        THUMBNAIL = "thumbnail", "Thumbnail"
        METADATA = "metadata", "Metadata"
        PLAYLIST = "playlist", "Playlist"
        CHANNEL = "channel", "Channel"

    class Priority(models.IntegerChoices):
        LOW = 0, "Low"
        NORMAL = 5, "Normal"
        HIGH = 10, "High"
        URGENT = 20, "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="downloads",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)

    # Source
    url = models.URLField(max_length=2048)
    platform = models.CharField(max_length=64, blank=True, db_index=True)
    platform_display = models.CharField(max_length=64, blank=True)
    extractor = models.CharField(max_length=64, blank=True)
    video_id = models.CharField(max_length=128, blank=True, db_index=True)

    # Metadata (populated after fetch)
    title = models.CharField(max_length=512, blank=True)
    description = models.TextField(blank=True)
    uploader = models.CharField(max_length=256, blank=True)
    uploader_id = models.CharField(max_length=128, blank=True)
    thumbnail_url = models.URLField(max_length=2048, blank=True)
    thumbnail_local = models.ImageField(upload_to="thumbnails/", blank=True, null=True)
    duration = models.PositiveIntegerField(null=True, blank=True)  # seconds
    view_count = models.BigIntegerField(null=True, blank=True)
    like_count = models.BigIntegerField(null=True, blank=True)
    upload_date = models.DateField(null=True, blank=True)
    webpage_url = models.URLField(max_length=2048, blank=True)
    is_live = models.BooleanField(default=False)
    is_playlist = models.BooleanField(default=False)
    playlist_count = models.PositiveIntegerField(null=True, blank=True)
    playlist_index = models.PositiveIntegerField(null=True, blank=True)
    chapters = models.JSONField(default=list, blank=True)
    subtitles_available = models.JSONField(default=list, blank=True)
    formats_available = models.JSONField(default=list, blank=True)
    raw_metadata = models.JSONField(default=dict, blank=True)

    # Options
    mode = models.CharField(max_length=32, choices=Mode.choices, default=Mode.VIDEO_AUDIO)
    quality = models.CharField(max_length=32, default="best")
    audio_quality = models.CharField(max_length=32, default="192")
    output_format = models.CharField(max_length=16, default="mp4")
    audio_format = models.CharField(max_length=16, default="mp3")
    selected_format_id = models.CharField(max_length=64, blank=True)
    subtitle_langs = models.JSONField(default=list, blank=True)
    embed_subs = models.BooleanField(default=False)
    embed_thumbnail = models.BooleanField(default=True)
    embed_metadata = models.BooleanField(default=True)
    write_description = models.BooleanField(default=False)
    write_thumbnail = models.BooleanField(default=False)
    playlist_start = models.PositiveIntegerField(null=True, blank=True)
    playlist_end = models.PositiveIntegerField(null=True, blank=True)
    custom_filename = models.CharField(max_length=512, blank=True)
    bandwidth_limit_kbps = models.PositiveIntegerField(default=0)

    # Progress
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    stage = models.CharField(max_length=64, blank=True)
    progress = models.FloatField(default=0.0)  # 0–100
    speed_bps = models.FloatField(null=True, blank=True)
    eta_seconds = models.IntegerField(null=True, blank=True)
    downloaded_bytes = models.BigIntegerField(default=0)
    total_bytes = models.BigIntegerField(null=True, blank=True)
    queue_position = models.PositiveIntegerField(null=True, blank=True)
    priority = models.IntegerField(choices=Priority.choices, default=Priority.NORMAL)
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)
    error_message = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)

    # Output
    file_path = models.CharField(max_length=1024, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    file_hash = models.CharField(max_length=64, blank=True)  # SHA-256
    resolution = models.CharField(max_length=32, blank=True)
    vcodec = models.CharField(max_length=64, blank=True)
    acodec = models.CharField(max_length=64, blank=True)
    fps = models.FloatField(null=True, blank=True)
    audio_bitrate = models.PositiveIntegerField(null=True, blank=True)

    # Organization
    folder = models.ForeignKey(
        Folder,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="downloads",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="downloads")
    is_favorite = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # soft delete
    notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["session_key", "status"]),
            models.Index(fields=["platform", "-created_at"]),
            models.Index(fields=["status", "priority", "created_at"]),
            models.Index(fields=["is_deleted", "-created_at"]),
            models.Index(fields=["video_id", "platform"]),
        ]
        verbose_name = "Download Job"
        verbose_name_plural = "Download Jobs"

    def __str__(self) -> str:
        return self.title or self.url[:80]

    @property
    def is_active(self) -> bool:
        return self.status in {
            self.Status.PENDING,
            self.Status.FETCHING_META,
            self.Status.QUEUED,
            self.Status.DOWNLOADING,
            self.Status.PROCESSING,
            self.Status.MERGING,
            self.Status.CONVERTING,
        }

    @property
    def can_pause(self) -> bool:
        return self.status in {self.Status.DOWNLOADING, self.Status.QUEUED}

    @property
    def can_resume(self) -> bool:
        return self.status == self.Status.PAUSED

    @property
    def can_cancel(self) -> bool:
        return self.status not in {
            self.Status.COMPLETED,
            self.Status.CANCELLED,
            self.Status.EXPIRED,
        }

    @property
    def progress_percent(self) -> int:
        return max(0, min(100, int(self.progress)))

    def mark_started(self) -> None:
        self.started_at = timezone.now()
        self.status = self.Status.DOWNLOADING
        self.save(update_fields=["started_at", "status", "updated_at"])

    def mark_completed(self, file_path: str, file_size: Optional[int] = None) -> None:
        self.status = self.Status.COMPLETED
        self.progress = 100.0
        self.file_path = file_path
        if file_size is not None:
            self.file_size = file_size
        self.completed_at = timezone.now()
        days = getattr(settings, "DOWNLOAD_EXPIRY_DAYS", 7)
        self.expires_at = timezone.now() + timezone.timedelta(days=days)
        self.error_message = ""
        self.save()

    def mark_failed(self, error: str) -> None:
        self.status = self.Status.FAILED
        self.error_message = error[:4000]
        self.save(update_fields=["status", "error_message", "updated_at"])

    def to_progress_dict(self) -> dict[str, Any]:
        """Payload for WebSocket / polling progress events."""
        from utils.format_utils import format_bytes, format_eta, format_speed

        pct = max(0.0, min(100.0, float(self.progress or 0)))
        # Prefer live totals; fall back to final file size when done
        total_bytes = self.total_bytes
        if total_bytes is None and self.file_size:
            total_bytes = self.file_size
        downloaded_bytes = self.downloaded_bytes or 0
        if self.status == self.Status.COMPLETED:
            pct = 100.0
            if self.file_size:
                downloaded_bytes = self.file_size
                total_bytes = self.file_size

        return {
            "id": str(self.id),
            "status": self.status,
            "stage": self.stage or self.status,
            "progress": round(pct, 1),
            "percent": round(pct, 1),
            "progress_percent": int(pct),
            "speed": format_speed(self.speed_bps),
            "speed_bps": self.speed_bps,
            "eta": format_eta(self.eta_seconds),
            "eta_seconds": self.eta_seconds,
            "downloaded": format_bytes(downloaded_bytes),
            "downloaded_bytes": downloaded_bytes,
            "total": format_bytes(total_bytes),
            "total_bytes": total_bytes,
            "queue_position": self.queue_position,
            "title": self.title,
            "error": self.error_message,
            "file_path": self.file_path if self.status == self.Status.COMPLETED else "",
            "is_active": self.is_active,
        }


class DownloadTemplate(models.Model):
    """Reusable download option presets."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="download_templates",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=64)
    is_default = models.BooleanField(default=False)
    options = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DuplicateFingerprint(models.Model):
    """Detect re-downloads of the same content."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duplicate_fingerprints",
        null=True,
        blank=True,
    )
    platform = models.CharField(max_length=64)
    video_id = models.CharField(max_length=128)
    quality = models.CharField(max_length=32, blank=True)
    mode = models.CharField(max_length=32, blank=True)
    download = models.ForeignKey(
        DownloadJob,
        on_delete=models.CASCADE,
        related_name="fingerprints",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "platform", "video_id"]),
        ]
        unique_together = [["user", "platform", "video_id", "quality", "mode"]]
