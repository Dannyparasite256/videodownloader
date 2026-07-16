"""Request audit logging middleware."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("audit")


class AuditLogMiddleware:
    """Attach request ID and log request/response metrics."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.request_id = request_id  # type: ignore[attr-defined]
        start = time.perf_counter()

        response = self.get_response(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response["X-Request-ID"] = request_id

        # Skip noisy static/health paths (Render probes /api/v1/health/ often)
        path = request.path
        if not path.startswith(("/static/", "/media/", "/health", "/api/v1/health")):
            user = getattr(request, "user", None)
            user_id = getattr(user, "pk", None) if user and user.is_authenticated else None
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "user_id": user_id,
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "ip": self._client_ip(request),
                },
            )
        return response

    @staticmethod
    def _client_ip(request: HttpRequest) -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")
