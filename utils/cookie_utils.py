"""YouTube Netscape cookies.txt quality checks."""
from __future__ import annotations

from pathlib import Path

# Session markers that indicate a logged-in Google/YouTube account (not just visitor IDs).
LOGIN_COOKIE_NAMES = frozenset(
    {
        "LOGIN_INFO",
        "SID",
        "__Secure-1PSID",
        "SAPISID",
        "APISID",
        "HSID",
        "SSID",
    }
)


def parse_cookie_names(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 6:
            names.add(parts[5].strip())
    return names


def cookie_jar_quality(text: str) -> dict:
    """
    Score a Netscape cookies.txt body for YouTube login usefulness.

    Returns keys: ok, score, max_score, has_youtube, names_found, missing, message
    """
    low = text.lower()
    names = parse_cookie_names(text)
    found = sorted(names & LOGIN_COOKIE_NAMES)
    missing = sorted(LOGIN_COOKIE_NAMES - names)
    has_youtube = "youtube" in low
    score = len(found)
    max_score = len(LOGIN_COOKIE_NAMES)
    # Require at least one strong session cookie + youtube domain
    ok = has_youtube and score >= 2 and len(text) > 200

    if not text.strip():
        message = "Cookie file is empty."
    elif not has_youtube:
        message = "File has no youtube.com cookies — export while on youtube.com."
    elif score == 0:
        message = (
            "File has YouTube visitor cookies only (not a logged-in session). "
            "Log into YouTube in Chrome, then re-export with “Get cookies.txt LOCALLY”."
        )
    elif score < 2:
        message = "Cookie session looks weak — re-export while fully logged into YouTube."
    else:
        message = f"Logged-in session cookies detected ({score}/{max_score})."

    return {
        "ok": ok,
        "score": score,
        "max_score": max_score,
        "has_youtube": has_youtube,
        "names_found": found,
        "missing": missing,
        "message": message,
    }


def cookie_file_quality(path: Path | str) -> dict:
    p = Path(path)
    if not p.is_file() or p.stat().st_size < 32:
        return {
            "ok": False,
            "score": 0,
            "max_score": len(LOGIN_COOKIE_NAMES),
            "has_youtube": False,
            "names_found": [],
            "missing": sorted(LOGIN_COOKIE_NAMES),
            "message": "No cookies file on disk.",
        }
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {
            "ok": False,
            "score": 0,
            "max_score": len(LOGIN_COOKIE_NAMES),
            "has_youtube": False,
            "names_found": [],
            "missing": sorted(LOGIN_COOKIE_NAMES),
            "message": "Could not read cookies file.",
        }
    return cookie_jar_quality(text)
