"""Downloads admin."""
from __future__ import annotations

from django.contrib import admin

from .models import DownloadJob, DownloadTemplate, DuplicateFingerprint, Folder, Tag


@admin.register(DownloadJob)
class DownloadJobAdmin(admin.ModelAdmin):
    list_display = (
        "short_title",
        "platform",
        "status",
        "mode",
        "quality",
        "progress",
        "user",
        "created_at",
    )
    list_filter = ("status", "platform", "mode", "is_favorite", "is_deleted", "created_at")
    search_fields = ("title", "url", "uploader", "video_id", "user__username")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "raw_metadata",
        "formats_available",
    )
    date_hierarchy = "created_at"
    raw_id_fields = ("user", "folder")
    list_per_page = 50

    @admin.display(description="Title")
    def short_title(self, obj: DownloadJob) -> str:
        t = obj.title or obj.url
        return t[:60] + ("…" if len(t) > 60 else "")


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "color", "created_at")
    search_fields = ("name", "user__username")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "color")
    search_fields = ("name",)


@admin.register(DownloadTemplate)
class DownloadTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "is_default", "created_at")


@admin.register(DuplicateFingerprint)
class DuplicateFingerprintAdmin(admin.ModelAdmin):
    list_display = ("platform", "video_id", "quality", "user", "created_at")
    search_fields = ("video_id", "platform")
