"""URL validation, platform detection, and sanitization helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

# Known host patterns → friendly platform names (yt-dlp handles extraction)
PLATFORM_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"(?:^|\.)youtube\.com$|youtu\.be$", re.I), "youtube", "YouTube"),
    (re.compile(r"(?:^|\.)tiktok\.com$", re.I), "tiktok", "TikTok"),
    (re.compile(r"(?:^|\.)(?:facebook|fb)\.com$|fb\.watch$", re.I), "facebook", "Facebook"),
    (re.compile(r"(?:^|\.)instagram\.com$", re.I), "instagram", "Instagram"),
    (re.compile(r"(?:^|\.)(?:twitter|x)\.com$", re.I), "twitter", "X (Twitter)"),
    (re.compile(r"(?:^|\.)vimeo\.com$", re.I), "vimeo", "Vimeo"),
    (re.compile(r"(?:^|\.)dailymotion\.com$|dai\.ly$", re.I), "dailymotion", "Dailymotion"),
    (re.compile(r"(?:^|\.)twitch\.tv$", re.I), "twitch", "Twitch"),
    (re.compile(r"(?:^|\.)reddit\.com$|redd\.it$", re.I), "reddit", "Reddit"),
    (re.compile(r"(?:^|\.)pinterest\.[a-z.]+$", re.I), "pinterest", "Pinterest"),
    (re.compile(r"(?:^|\.)soundcloud\.com$", re.I), "soundcloud", "SoundCloud"),
    (re.compile(r"(?:^|\.)mixcloud\.com$", re.I), "mixcloud", "Mixcloud"),
    (re.compile(r"(?:^|\.)bilibili\.com$|b23\.tv$", re.I), "bilibili", "Bilibili"),
    (re.compile(r"(?:^|\.)vk\.com$|vk\.ru$", re.I), "vk", "VK"),
    (re.compile(r"(?:^|\.)tumblr\.com$", re.I), "tumblr", "Tumblr"),
    (re.compile(r"(?:^|\.)threads\.net$", re.I), "threads", "Threads"),
    (re.compile(r"(?:^|\.)snapchat\.com$", re.I), "snapchat", "Snapchat"),
    (re.compile(r"(?:^|\.)streamable\.com$", re.I), "streamable", "Streamable"),
    (re.compile(r"(?:^|\.)loom\.com$", re.I), "loom", "Loom"),
    (re.compile(r"(?:^|\.)ted\.com$", re.I), "ted", "TED"),
    (re.compile(r"(?:^|\.)archive\.org$", re.I), "archive", "Archive.org"),
]

URL_RE = re.compile(
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}|"
    r"localhost|"
    r"\d{1,3}(?:\.\d{1,3}){3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)

FILENAME_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class PlatformInfo:
    """Detected platform metadata for a URL."""

    slug: str
    display_name: str
    host: str
    is_known: bool


def is_valid_url(url: str) -> bool:
    """Return True if *url* looks like a valid HTTP(S) URL."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if len(url) > 2048:
        return False
    if not URL_RE.match(url):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def detect_platform(url: str) -> PlatformInfo:
    """Detect platform from URL host. Falls back to host-based generic label."""
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]

    for pattern, slug, display in PLATFORM_PATTERNS:
        if pattern.search(host):
            return PlatformInfo(slug=slug, display_name=display, host=host, is_known=True)

    # Generic: use second-level domain as label
    parts = host.split(".")
    slug = parts[-2] if len(parts) >= 2 else host or "unknown"
    display = slug.replace("-", " ").title()
    return PlatformInfo(slug=slug, display_name=display, host=host, is_known=False)


def sanitize_filename(name: str, max_length: int = 180) -> str:
    """Sanitize a string for use as a filesystem filename."""
    if not name:
        return "download"
    name = FILENAME_UNSAFE.sub("_", name)
    name = name.strip(" .")
    name = re.sub(r"\s+", " ", name)
    if len(name) > max_length:
        name = name[:max_length].rstrip()
    return name or "download"


def normalize_url(url: str) -> str:
    """Strip whitespace and trailing fragments noise from a URL."""
    url = url.strip()
    # Keep fragment only if meaningful; yt-dlp handles most cases
    return url


def extract_urls_from_text(text: str) -> list[str]:
    """Extract HTTP(S) URLs from free-form text (bulk paste)."""
    found = re.findall(r"https?://[^\s<>\"']+", text or "")
    return [u.rstrip(".,);]") for u in found if is_valid_url(u.rstrip(".,);]"))]
