"""Custom error handlers and shared utility views."""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def bad_request(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "errors/400.html", status=400)


def permission_denied(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "errors/403.html", status=403)


def page_not_found(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "errors/404.html", status=404)


def server_error(request: HttpRequest) -> HttpResponse:
    """Never let the error page itself raise — that becomes a blank 500."""
    try:
        return render(request, "errors/500.html", status=500)
    except Exception:
        return HttpResponse(
            "<!DOCTYPE html><html><body style='font-family:system-ui;text-align:center;"
            "padding:3rem;background:#06060a;color:#e2e8f0'>"
            "<h1>500</h1><p>Something went wrong. Refresh or go home.</p>"
            "<p><a href='/' style='color:#a5b4fc'>Go home</a></p>"
            "</body></html>",
            status=500,
            content_type="text/html",
        )
