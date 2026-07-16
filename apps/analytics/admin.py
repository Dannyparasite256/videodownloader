from django.contrib import admin

from .models import DailyStats


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "user",
        "downloads_started",
        "downloads_completed",
        "downloads_failed",
        "bytes_downloaded",
    )
    list_filter = ("date",)
    date_hierarchy = "date"
