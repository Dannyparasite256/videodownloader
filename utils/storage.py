"""Static file storage helpers for production (WhiteNoise-compatible)."""
from __future__ import annotations

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Like CompressedManifestStaticFilesStorage, but missing manifest entries
    fall back to the plain path instead of crashing the whole request.

    Prevents production 500s like:
    ValueError: Missing staticfiles manifest entry for 'js/theme-boot.js'
    when a static file is added and collectstatic is slightly out of date.
    """

    manifest_strict = False
