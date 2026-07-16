"""Notification list and mark-read views."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import Notification


@login_required
@require_GET
def list_notifications(request: HttpRequest) -> HttpResponse:
    notes = request.user.notifications.all()[:50]
    if request.headers.get("HX-Request"):
        return render(request, "notifications/partials/list.html", {"notifications": notes})
    return render(request, "notifications/list.html", {"notifications": notes})


@login_required
@require_POST
def mark_read(request: HttpRequest, pk: str) -> HttpResponse:
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    note.is_read = True
    note.save(update_fields=["is_read"])
    if request.headers.get("HX-Request"):
        return HttpResponse(status=204)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request: HttpRequest) -> HttpResponse:
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications:list")


@login_required
@require_GET
def unread_count(request: HttpRequest) -> JsonResponse:
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({"count": count})
