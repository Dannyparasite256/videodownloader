"""Template context processors."""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest


def site_settings(request: HttpRequest) -> dict[str, Any]:
    """Expose site-wide settings to all templates."""
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "VideoDL Pro"),
        "SITE_URL": getattr(settings, "SITE_URL", ""),
        "DOWNLOAD_DISCLAIMER": getattr(settings, "DOWNLOAD_DISCLAIMER", ""),
        "DEBUG": settings.DEBUG,
    }
