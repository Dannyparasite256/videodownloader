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
        from utils.cookie_utils import cookie_file_quality, cookie_jar_quality

        p = Path(settings.BASE_DIR) / "secrets" / "cookies.txt"
        cookies_ok = cookie_file_quality(p)["ok"]
        if not cookies_ok:
            # Env base64 may be present before file materializes
            b64 = (getattr(settings, "YTDLP_COOKIES_BASE64", "") or "").strip()
            if b64:
                import base64

                try:
                    raw = base64.b64decode(b64)
                    cookies_ok = cookie_jar_quality(
                        raw.decode("utf-8", errors="replace")
                    )["ok"]
                except Exception:
                    cookies_ok = False
    except Exception:
        cookies_ok = False

    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "VideoDL Pro"),
        "SITE_URL": getattr(settings, "SITE_URL", ""),
        "DOWNLOAD_DISCLAIMER": getattr(settings, "DOWNLOAD_DISCLAIMER", ""),
        "DEBUG": settings.DEBUG,
        "IS_RENDER": getattr(settings, "IS_RENDER", False),
        "RENDER_FREE_TIER": getattr(settings, "RENDER_FREE_TIER", False),
        "YOUTUBE_COOKIES_OK": cookies_ok,
    }
