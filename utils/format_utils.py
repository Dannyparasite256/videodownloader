"""Human-readable formatting helpers for sizes, durations, speeds."""
from __future__ import annotations

from typing import Optional


def format_bytes(num: Optional[int | float], precision: int = 1) -> str:
    """Format byte count as human-readable string (e.g. 1.5 GB)."""
    if num is None or num < 0:
        return "—"
    num = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0:
            if unit == "B":
                return f"{int(num)} {unit}"
            return f"{num:.{precision}f} {unit}"
        num /= 1024.0
    return f"{num:.{precision}f} PB"


def format_speed(bps: Optional[float]) -> str:
    """Format bytes/second as human-readable speed."""
    if bps is None or bps <= 0:
        return "—"
    return f"{format_bytes(bps)}/s"


def format_duration(seconds: Optional[float | int]) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_eta(seconds: Optional[float | int]) -> str:
    """Format ETA seconds as compact string."""
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h}h {m}m"


def resolution_label(height: Optional[int], width: Optional[int] = None) -> str:
    """Map height to common resolution label (720p, 1080p, 4K, …)."""
    if not height:
        return "Unknown"
    mapping = {
        144: "144p",
        240: "240p",
        360: "360p",
        480: "480p",
        720: "720p",
        1080: "1080p",
        1440: "1440p",
        2160: "4K",
        4320: "8K",
    }
    if height in mapping:
        return mapping[height]
    # Nearest known tier
    for h in sorted(mapping.keys()):
        if height <= h:
            return mapping[h]
    return f"{height}p"
