"""Web views for home, history, file manager, and download actions."""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.downloads.models import DownloadJob, Folder, Tag
from repositories.download_repository import DownloadRepository
from services.download_service import DownloadService, DownloadServiceError
from utils.url_utils import extract_urls_from_text, is_valid_url


def _session_key(request: HttpRequest) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


def _get_job_for_request(request: HttpRequest, job_id: str) -> DownloadJob:
    repo = DownloadRepository()
    job = repo.get_by_id(job_id)
    if not job:
        raise Http404
    user = request.user
    if user.is_authenticated:
        if job.user_id != user.id and not user.is_staff:
            raise Http404
    else:
        # Guests: match session when set; allow empty-session legacy rows
        sk = _session_key(request)
        if job.user_id is not None:
            raise Http404
        if job.session_key and job.session_key != sk:
            raise Http404
    return job


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """Premium landing / download page."""
    import json

    video_formats = ["mp4", "mkv", "webm", "mov", "avi"]
    audio_formats = ["mp3", "m4a", "aac", "flac", "wav", "ogg", "opus"]
    return render(
        request,
        "downloads/home.html",
        {
            "disclaimer": settings.DOWNLOAD_DISCLAIMER,
            "qualities": [
                ("best", "Highest Available"),
                ("2160", "4K (2160p)"),
                ("1440", "1440p"),
                ("1080", "1080p"),
                ("720", "720p"),
                ("480", "480p"),
                ("360", "360p"),
                ("240", "240p"),
                ("144", "144p"),
                ("worst", "Lowest Available"),
            ],
            "audio_qualities": [
                ("best", "Best"),
                ("320", "320 kbps"),
                ("256", "256 kbps"),
                ("192", "192 kbps"),
                ("128", "128 kbps"),
                ("96", "96 kbps"),
                ("64", "64 kbps"),
            ],
            "video_formats": video_formats,
            "audio_formats": audio_formats,
            "video_formats_json": json.dumps(video_formats),
            "audio_formats_json": json.dumps(audio_formats),
            "modes": DownloadJob.Mode.choices,
        },
    )


@require_POST
def fetch_metadata(request: HttpRequest) -> JsonResponse:
    """AJAX/HTMX: validate URL and return metadata + formats."""
    url = (request.POST.get("url") or request.GET.get("url") or "").strip()
    if not is_valid_url(url):
        return JsonResponse({"ok": False, "error": "Please enter a valid URL."}, status=400)
    try:
        meta = DownloadService().fetch_metadata(url)
        return JsonResponse({"ok": True, "data": meta})
    except DownloadServiceError as exc:
        return JsonResponse({"ok": False, "error": str(exc), "code": exc.code}, status=400)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)


@require_POST
def start_download(request: HttpRequest) -> HttpResponse:
    """Create a download job from the form / HTMX."""
    url = (request.POST.get("url") or "").strip()
    mode = request.POST.get("mode") or DownloadJob.Mode.VIDEO_AUDIO
    quality = request.POST.get("quality") or "best"
    audio_quality = request.POST.get("audio_quality") or "192"
    output_format = request.POST.get("output_format") or "mp4"
    audio_format = request.POST.get("audio_format") or "mp3"
    format_id = request.POST.get("format_id") or ""
    check_dup = request.POST.get("check_duplicate") != "0"

    # Optional pre-fetched metadata JSON fields
    metadata = {
        "title": request.POST.get("title") or "",
        "thumbnail": request.POST.get("thumbnail") or "",
        "uploader": request.POST.get("uploader") or "",
        "duration": _int_or_none(request.POST.get("duration")),
        "video_id": request.POST.get("video_id") or "",
        "platform": request.POST.get("platform") or "",
        "platform_display": request.POST.get("platform_display") or "",
        "view_count": _int_or_none(request.POST.get("view_count")),
        "like_count": _int_or_none(request.POST.get("like_count")),
    }

    try:
        job = DownloadService().create_download(
            url,
            user=request.user,
            session_key=_session_key(request),
            mode=mode,
            quality=quality,
            audio_quality=audio_quality,
            output_format=output_format,
            audio_format=audio_format,
            selected_format_id=format_id,
            embed_subs=request.POST.get("embed_subs") == "on",
            embed_thumbnail=request.POST.get("embed_thumbnail", "on") == "on",
            write_description=request.POST.get("write_description") == "on",
            write_thumbnail=request.POST.get("write_thumbnail") == "on",
            playlist_start=_int_or_none(request.POST.get("playlist_start")),
            playlist_end=_int_or_none(request.POST.get("playlist_end")),
            metadata=metadata if metadata.get("title") or metadata.get("video_id") else None,
            check_duplicate=check_dup,
        )
    except DownloadServiceError as exc:
        if request.headers.get("HX-Request"):
            return HttpResponse(
                f'<div class="toast-error">{exc}</div>',
                status=400,
            )
        messages.error(request, str(exc))
        return redirect("downloads:home")

    if request.headers.get("HX-Request") or request.headers.get("Accept") == "application/json":
        if "application/json" in (request.headers.get("Accept") or ""):
            return JsonResponse({"ok": True, "id": str(job.id), "status": job.status})
        return render(request, "downloads/partials/job_card.html", {"job": job})

    messages.success(request, "Download started.")
    return redirect("downloads:detail", job_id=job.id)


@require_POST
def bulk_download(request: HttpRequest) -> HttpResponse:
    text = request.POST.get("urls") or ""
    urls = extract_urls_from_text(text)
    if not urls:
        messages.error(request, "No valid URLs found.")
        return redirect("downloads:home")
    jobs = DownloadService().create_bulk(
        urls,
        user=request.user,
        session_key=_session_key(request),
        mode=request.POST.get("mode") or DownloadJob.Mode.VIDEO_AUDIO,
        quality=request.POST.get("quality") or "best",
        check_duplicate=False,
    )
    messages.success(request, f"Queued {len(jobs)} download(s).")
    return redirect("downloads:history")


@require_GET
def detail(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _get_job_for_request(request, job_id)
    return render(request, "downloads/detail.html", {"job": job})


@require_GET
def history(request: HttpRequest) -> HttpResponse:
    repo = DownloadRepository()
    qs = repo.list_history(
        request.user,
        session_key=_session_key(request),
        search=request.GET.get("q", ""),
        status=request.GET.get("status", ""),
        platform=request.GET.get("platform", ""),
        favorite=True if request.GET.get("favorite") == "1" else None,
        ordering=request.GET.get("sort", "-created_at"),
    )
    # Simple pagination
    page = max(1, int(request.GET.get("page", 1) or 1))
    per_page = 20
    total = qs.count()
    items = list(qs[(page - 1) * per_page : page * per_page])
    return render(
        request,
        "downloads/history.html",
        {
            "jobs": items,
            "page": page,
            "total": total,
            "has_next": page * per_page < total,
            "has_prev": page > 1,
            "filters": {
                "q": request.GET.get("q", ""),
                "status": request.GET.get("status", ""),
                "platform": request.GET.get("platform", ""),
                "favorite": request.GET.get("favorite", ""),
                "sort": request.GET.get("sort", "-created_at"),
            },
            "statuses": DownloadJob.Status.choices,
        },
    )


@require_POST
def pause_download(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _get_job_for_request(request, job_id)
    try:
        DownloadService().pause(job)
        messages.info(request, "Download paused.")
    except DownloadServiceError as exc:
        messages.error(request, str(exc))
    return _action_response(request, job)


@require_POST
def resume_download(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _get_job_for_request(request, job_id)
    try:
        DownloadService().resume(job)
        messages.info(request, "Download resumed.")
    except DownloadServiceError as exc:
        messages.error(request, str(exc))
    return _action_response(request, job)


@require_POST
def cancel_download(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _get_job_for_request(request, job_id)
    try:
        DownloadService().cancel(job)
        messages.info(request, "Download cancelled.")
    except DownloadServiceError as exc:
        messages.error(request, str(exc))
    return _action_response(request, job)


@require_POST
def retry_download(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _get_job_for_request(request, job_id)
    try:
        DownloadService().retry(job)
        messages.success(request, "Retry queued.")
    except DownloadServiceError as exc:
        messages.error(request, str(exc))
    return _action_response(request, job)


@require_POST
def redownload(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _get_job_for_request(request, job_id)
    new_job = DownloadService().redownload(job)
    messages.success(request, "Re-download started.")
    return redirect("downloads:detail", job_id=new_job.id)


@require_POST
def delete_download(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _get_job_for_request(request, job_id)
    DownloadRepository().soft_delete(job)
    messages.success(request, "Moved to trash.")
    return redirect("downloads:history")


@require_POST
def toggle_favorite(request: HttpRequest, job_id: str) -> HttpResponse:
    job = _get_job_for_request(request, job_id)
    job.is_favorite = not job.is_favorite
    job.save(update_fields=["is_favorite", "updated_at"])
    if request.headers.get("HX-Request"):
        return render(request, "downloads/partials/favorite_btn.html", {"job": job})
    return redirect("downloads:detail", job_id=job.id)


@require_GET
def download_file(request: HttpRequest, job_id: str) -> HttpResponse:
    """Stream completed file to the client."""
    job = _get_job_for_request(request, job_id)
    if job.status != DownloadJob.Status.COMPLETED or not job.file_path:
        raise Http404("File not ready")
    path = Path(job.file_path)
    if not path.exists():
        raise Http404("File missing from storage")
    content_type, _ = mimetypes.guess_type(str(path))
    response = FileResponse(
        open(path, "rb"),
        as_attachment=True,
        filename=path.name,
        content_type=content_type or "application/octet-stream",
    )
    return response


@require_GET
def progress_json(request: HttpRequest, job_id: str) -> JsonResponse:
    """Live progress snapshot for polling (percent, speed, ETA, sizes)."""
    job = _get_job_for_request(request, job_id)
    # Fresh DB read — avoid stale cached instances during concurrent download writes
    job.refresh_from_db()
    response = JsonResponse(job.to_progress_dict())
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


@login_required
@require_GET
def file_manager(request: HttpRequest) -> HttpResponse:
    jobs = (
        DownloadJob.objects.filter(
            user=request.user,
            status=DownloadJob.Status.COMPLETED,
            is_deleted=False,
        )
        .order_by("-completed_at")[:100]
    )
    folders = Folder.objects.filter(user=request.user)
    return render(
        request,
        "downloads/file_manager.html",
        {"jobs": jobs, "folders": folders},
    )


@require_GET
def qr_code(request: HttpRequest, job_id: str) -> HttpResponse:
    """Generate QR code PNG linking to the download file URL."""
    import io

    import qrcode
    from django.urls import reverse

    job = _get_job_for_request(request, job_id)
    url = request.build_absolute_uri(reverse("downloads:file", kwargs={"job_id": job.id}))
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


def _action_response(request: HttpRequest, job: DownloadJob) -> HttpResponse:
    if request.headers.get("HX-Request"):
        return render(request, "downloads/partials/job_card.html", {"job": job})
    return redirect("downloads:detail", job_id=job.id)


def _int_or_none(val) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None
