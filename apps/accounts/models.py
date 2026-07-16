"""Custom user model and profile for VideoDL Pro."""
from __future__ import annotations

import secrets
import uuid
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """Extended user with preferences, storage quota, and API access."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.CharField(max_length=280, blank=True)

    # Theme preferences
    theme = models.CharField(
        max_length=16,
        choices=[("system", "System"), ("light", "Light"), ("dark", "Dark")],
        default="system",
    )
    accent_color = models.CharField(max_length=7, default="#6366f1")  # indigo-500

    # Quotas
    storage_quota_mb = models.PositiveIntegerField(default=5120)
    storage_used_bytes = models.BigIntegerField(default=0)
    max_concurrent_downloads = models.PositiveSmallIntegerField(default=3)
    bandwidth_limit_kbps = models.PositiveIntegerField(
        default=0,
        help_text="0 = unlimited",
    )

    # Flags
    is_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    browser_notifications = models.BooleanField(default=True)

    # Default download preferences
    default_video_quality = models.CharField(max_length=32, default="best")
    default_audio_quality = models.CharField(max_length=32, default="192")
    default_format = models.CharField(max_length=16, default="mp4")
    preferred_filename_template = models.CharField(
        max_length=255,
        default="%(title)s [%(id)s].%(ext)s",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_blocked"]),
            models.Index(fields=["-date_joined"]),
        ]

    def __str__(self) -> str:
        return self.username

    @property
    def storage_used_mb(self) -> float:
        return self.storage_used_bytes / (1024 * 1024)

    @property
    def storage_remaining_bytes(self) -> int:
        return max(0, self.storage_quota_mb * 1024 * 1024 - self.storage_used_bytes)

    @property
    def storage_usage_percent(self) -> float:
        quota = self.storage_quota_mb * 1024 * 1024
        if quota <= 0:
            return 0.0
        return min(100.0, (self.storage_used_bytes / quota) * 100)


class APIKey(models.Model):
    """User-generated API keys for programmatic access."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=64)
    key_prefix = models.CharField(max_length=8, editable=False)
    key_hash = models.CharField(max_length=128, editable=False)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self) -> str:
        return f"{self.name} ({self.key_prefix}…)"

    @classmethod
    def generate(cls, user: User, name: str, scopes: list[str] | None = None) -> tuple["APIKey", str]:
        """Create an API key and return (instance, raw_key). Raw key shown once."""
        import hashlib

        raw = f"vdl_{secrets.token_urlsafe(32)}"
        prefix = raw[:8]
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        obj = cls.objects.create(
            user=user,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=scopes or ["download:read", "download:write"],
        )
        return obj, raw


class ActivityLog(models.Model):
    """User activity audit trail."""

    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout"
        DOWNLOAD_CREATE = "download_create", "Download Created"
        DOWNLOAD_COMPLETE = "download_complete", "Download Completed"
        DOWNLOAD_FAIL = "download_fail", "Download Failed"
        SETTINGS_UPDATE = "settings_update", "Settings Updated"
        API_KEY_CREATE = "api_key_create", "API Key Created"
        API_KEY_REVOKE = "api_key_revoke", "API Key Revoked"
        PROFILE_UPDATE = "profile_update", "Profile Updated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="activity_logs",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at}"
