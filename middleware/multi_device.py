"""Helpers so the app works from phones, LAN, and public tunnels."""
from __future__ import annotations

from typing import Callable
from urllib.parse import urlparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class MultiDeviceCSRFMiddleware:
    """
    Trust CSRF origins for LAN IPs and Cloudflare quick tunnels when
    ALLOW_MULTI_DEVICE is enabled. Runs before CsrfViewMiddleware so that
    request.META / trusted origins stay flexible without listing every host.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if getattr(settings, "ALLOW_MULTI_DEVICE", False):
            origin = request.META.get("HTTP_ORIGIN") or request.META.get("HTTP_REFERER")
            if origin:
                parsed = urlparse(origin)
                host = (parsed.hostname or "").lower()
                scheme = parsed.scheme or "http"
                port = parsed.port
                if host and self._is_trusted_host(host):
                    if port and port not in (80, 443):
                        origin_url = f"{scheme}://{host}:{port}"
                    else:
                        origin_url = f"{scheme}://{host}"
                    trusted = list(getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or [])
                    if origin_url not in trusted:
                        # Mutate a copy on the request so Django's check can see it
                        # via settings — update module-level list for this process.
                        if origin_url not in settings.CSRF_TRUSTED_ORIGINS:
                            settings.CSRF_TRUSTED_ORIGINS.append(origin_url)
        return self.get_response(request)

    @staticmethod
    def _is_trusted_host(host: str) -> bool:
        if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
            return True
        if host.endswith(".trycloudflare.com") or host.endswith(".cfargotunnel.com"):
            return True
        # Render public hostnames
        if host.endswith(".onrender.com"):
            return True
        # Private / link-local IPv4
        parts = host.split(".")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            a, b = int(parts[0]), int(parts[1])
            if a == 10:
                return True
            if a == 172 and 16 <= b <= 31:
                return True
            if a == 192 and b == 168:
                return True
            if a == 169 and b == 254:
                return True
        return False
