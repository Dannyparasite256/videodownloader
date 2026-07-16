"""Accounts admin."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import APIKey, ActivityLog, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "is_staff",
        "is_blocked",
        "storage_used_mb_display",
        "date_joined",
    )
    list_filter = ("is_staff", "is_blocked", "is_verified", "theme", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("storage_used_bytes", "created_at", "updated_at", "last_active_at")

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Preferences",
            {
                "fields": (
                    "theme",
                    "accent_color",
                    "avatar",
                    "bio",
                    "default_video_quality",
                    "default_audio_quality",
                    "default_format",
                    "preferred_filename_template",
                )
            },
        ),
        (
            "Quotas & Limits",
            {
                "fields": (
                    "storage_quota_mb",
                    "storage_used_bytes",
                    "max_concurrent_downloads",
                    "bandwidth_limit_kbps",
                )
            },
        ),
        (
            "Flags",
            {
                "fields": (
                    "is_verified",
                    "is_blocked",
                    "email_notifications",
                    "browser_notifications",
                )
            },
        ),
    )

    @admin.display(description="Storage Used (MB)")
    def storage_used_mb_display(self, obj: User) -> str:
        return f"{obj.storage_used_mb:.1f}"


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "key_prefix", "is_active", "created_at", "last_used_at")
    list_filter = ("is_active",)
    search_fields = ("name", "user__username", "key_prefix")
    readonly_fields = ("key_prefix", "key_hash", "created_at")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "ip_address", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "description", "ip_address")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
