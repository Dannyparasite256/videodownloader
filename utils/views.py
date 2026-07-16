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
    return render(request, "errors/500.html", status=500)
