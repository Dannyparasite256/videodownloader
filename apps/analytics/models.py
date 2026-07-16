"""Aggregated analytics snapshots."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class DailyStats(models.Model):
    """Per-user (or global) daily download statistics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_stats",
        null=True,
        blank=True,
        help_text="Null = global aggregate",
    )
    date = models.DateField(db_index=True)
    downloads_started = models.PositiveIntegerField(default=0)
    downloads_completed = models.PositiveIntegerField(default=0)
    downloads_failed = models.PositiveIntegerField(default=0)
    bytes_downloaded = models.BigIntegerField(default=0)
    avg_speed_bps = models.FloatField(null=True, blank=True)
    platform_breakdown = models.JSONField(default=dict, blank=True)
    format_breakdown = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = [["user", "date"]]
        verbose_name_plural = "Daily stats"

    def __str__(self) -> str:
        who = self.user_id or "global"
        return f"{who} @ {self.date}"
