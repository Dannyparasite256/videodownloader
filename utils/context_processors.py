"""Template context processors."""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest


def site_settings(request: HttpRequest) -> dict[str, Any]:
    """Expose site-wide settings to all templates."""
    from pathlib import Path

    cookies_ok = False
    try:
        p = Path(settings.BASE_DIR) / "secrets" / "cookies.txt"
        cookies_ok = p.is_file() and p.stat().st_size > 32
    except Exception:
        cookies_ok = False
    if not cookies_ok:
        cookies_ok = bool(getattr(settings, "YTDLP_COOKIES_BASE64", ""))

    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "VideoDL Pro"),
        "SITE_URL": getattr(settings, "SITE_URL", ""),
        "DOWNLOAD_DISCLAIMER": getattr(settings, "DOWNLOAD_DISCLAIMER", ""),
        "DEBUG": settings.DEBUG,
        "IS_RENDER": getattr(settings, "IS_RENDER", False),
        "RENDER_FREE_TIER": getattr(settings, "RENDER_FREE_TIER", False),
        "YOUTUBE_COOKIES_OK": cookies_ok,
    }
