"""Lazy Cloudflare WARP SOCKS helper for cloud hosts (Render free tier)."""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_started = False


def ensure_warp_proxy() -> str:
    """
    Ensure local WARP SOCKS is up when ENABLE_WARP_PROXY is set.
    Returns proxy URL (may be empty if disabled / unavailable).
    """
    global _started

    proxy = (os.environ.get("YTDLP_PROXY") or "").strip()
    enabled = os.environ.get("ENABLE_WARP_PROXY", "True").lower() in {
        "1",
        "true",
        "yes",
    }
    if not enabled:
        return proxy

    if not proxy:
        proxy = "socks5://127.0.0.1:1080"
        os.environ["YTDLP_PROXY"] = proxy

    # Already started this process
    if _started:
        return proxy

    with _lock:
        if _started:
            return proxy
        script = Path(__file__).resolve().parents[1] / "scripts" / "start_warp_proxy.sh"
        if not script.is_file():
            logger.warning("WARP script missing: %s", script)
            _started = True
            return proxy
        try:
            logger.info("Starting WARP SOCKS proxy (lazy)…")
            subprocess.Popen(
                ["bash", str(script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Brief settle — do not block long
            time.sleep(4)
            _started = True
            logger.info("WARP start requested; using %s", proxy)
        except Exception as exc:
            logger.warning("Could not start WARP: %s", exc)
            _started = True
    return proxy
