"""
Download service layer – orchestrates metadata, queue, and job lifecycle.

Respects platform Terms of Service and copyright: this service only initiates
downloads of publicly available streams that yt-dlp can access without DRM bypass.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.utils import timezone

from apps.downloads.models import DownloadJob
from apps.downloader.engine import DownloadEngine, VideoMetadata
from apps.downloader.progress import broadcast_progress, broadcast_user_event
from repositories.download_repository import DownloadRepository
from utils.url_utils import detect_platform, is_valid_url, normalize_url

logger = logging.getLogger(__name__)

# Throttle DB + WS progress writes so UI stays smooth under high hook frequency
_PROGRESS_MIN_INTERVAL = 0.4  # seconds


class DownloadServiceError(Exception):
    """Domain error for download operations."""

    def __init__(self, message: str, code: str = "error") -> None:
        super().__init__(message)
        self.code = code


class DownloadService:
    """Application service for download use-cases."""

    def __init__(self, repo: Optional[DownloadRepository] = None) -> None:
        self.repo = repo or DownloadRepository()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def fetch_metadata(self, url: str, *, use_cache: bool = True) -> dict[str, Any]:
        url = normalize_url(url)
        if not is_valid_url(url):
            raise DownloadServiceError("Invalid URL", code="invalid_url")

        cache_key = f"meta:{hash(url)}"
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        engine = DownloadEngine()
        try:
            meta: VideoMetadata = engine.extract_metadata(url)
        except Exception as exc:
            from apps.downloader.engine import humanize_ytdlp_error

            friendly = humanize_ytdlp_error(exc)
            logger.warning("Metadata extraction failed for %s: %s", url, exc)
            code = "metadata_failed"
            if "bot" in friendly.lower() or "cookies" in friendly.lower():
                code = "youtube_bot"
            raise DownloadServiceError(friendly, code=code) from exc

        data = meta.to_dict()
        cache.set(cache_key, data, timeout=300)
        return data

    # ------------------------------------------------------------------
    # Create / queue
    # ------------------------------------------------------------------
    @transaction.atomic
    def create_download(
        self,
        url: str,
        *,
        user=None,
        session_key: str = "",
        mode: str = DownloadJob.Mode.VIDEO_AUDIO,
        quality: str = "best",
        audio_quality: str = "192",
        output_format: str = "mp4",
        audio_format: str = "mp3",
        selected_format_id: str = "",
        subtitle_langs: Optional[list[str]] = None,
        embed_subs: bool = False,
        embed_thumbnail: bool = True,
        embed_metadata: bool = True,
        write_description: bool = False,
        write_thumbnail: bool = False,
        playlist_start: Optional[int] = None,
        playlist_end: Optional[int] = None,
        priority: int = DownloadJob.Priority.NORMAL,
        bandwidth_limit_kbps: int = 0,
        folder_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        check_duplicate: bool = True,
    ) -> DownloadJob:
        url = normalize_url(url)
        if not is_valid_url(url):
            raise DownloadServiceError("Invalid URL", code="invalid_url")

        if user and getattr(user, "is_blocked", False):
            raise DownloadServiceError("Account is blocked", code="blocked")

        # Concurrency / quota checks
        max_concurrent = getattr(settings, "MAX_CONCURRENT_DOWNLOADS", 5)
        if user and user.is_authenticated:
            max_concurrent = min(max_concurrent, user.max_concurrent_downloads)
            if user.storage_remaining_bytes <= 0:
                raise DownloadServiceError("Storage quota exceeded", code="quota")
        else:
            # Guest daily limit
            guest_limit = getattr(settings, "GUEST_MAX_DOWNLOADS_PER_DAY", 5)
            if session_key:
                day_key = f"guest_dl:{session_key}:{timezone.now().date()}"
                count = cache.get(day_key, 0)
                if count >= guest_limit:
                    raise DownloadServiceError(
                        "Guest daily download limit reached. Please sign in.",
                        code="guest_limit",
                    )

        platform = detect_platform(url)
        meta = metadata or {}

        if check_duplicate and meta.get("video_id"):
            dup = self.repo.find_duplicate(
                user,
                meta.get("platform") or platform.slug,
                meta["video_id"],
                quality,
                mode,
            )
            if dup:
                raise DownloadServiceError(
                    f"Already downloaded: {dup.title}",
                    code="duplicate",
                )

        job = self.repo.create(
            user=user if user and user.is_authenticated else None,
            session_key=session_key or "",
            url=url,
            platform=meta.get("platform") or platform.slug,
            platform_display=meta.get("platform_display") or platform.display_name,
            extractor=meta.get("extractor") or "",
            video_id=meta.get("video_id") or "",
            title=meta.get("title") or "",
            description=(meta.get("description") or "")[:5000],
            uploader=meta.get("uploader") or "",
            uploader_id=meta.get("uploader_id") or "",
            thumbnail_url=meta.get("thumbnail") or "",
            duration=meta.get("duration"),
            view_count=meta.get("view_count"),
            like_count=meta.get("like_count"),
            upload_date=meta.get("upload_date") or None,
            webpage_url=meta.get("webpage_url") or url,
            is_live=bool(meta.get("is_live")),
            is_playlist=bool(meta.get("is_playlist")),
            playlist_count=meta.get("playlist_count"),
            chapters=meta.get("chapters") or [],
            subtitles_available=meta.get("subtitles") or [],
            formats_available=meta.get("formats") or [],
            raw_metadata=meta.get("raw") or {},
            mode=mode,
            quality=quality,
            audio_quality=audio_quality,
            output_format=output_format,
            audio_format=audio_format,
            selected_format_id=selected_format_id,
            subtitle_langs=subtitle_langs or [],
            embed_subs=embed_subs,
            embed_thumbnail=embed_thumbnail,
            embed_metadata=embed_metadata,
            write_description=write_description,
            write_thumbnail=write_thumbnail,
            playlist_start=playlist_start,
            playlist_end=playlist_end,
            priority=priority,
            bandwidth_limit_kbps=bandwidth_limit_kbps
            or (user.bandwidth_limit_kbps if user and user.is_authenticated else 0),
            status=DownloadJob.Status.QUEUED,
            stage="queued",
        )

        if folder_id and user and user.is_authenticated:
            from apps.downloads.models import Folder

            folder = Folder.objects.filter(id=folder_id, user=user).first()
            if folder:
                job.folder = folder
                job.save(update_fields=["folder"])

        # Increment guest counter
        if not (user and user.is_authenticated) and session_key:
            day_key = f"guest_dl:{session_key}:{timezone.now().date()}"
            try:
                cache.incr(day_key)
            except ValueError:
                cache.set(day_key, 1, timeout=86400)

        # Dispatch AFTER commit so background workers can read the row
        job_id = str(job.id)

        def _after_commit() -> None:
            task_id = self._dispatch_job(job_id)
            DownloadJob.objects.filter(id=job_id).update(celery_task_id=task_id)
            logger.info("Queued download %s for %s (task=%s)", job_id, url, task_id)

        transaction.on_commit(_after_commit)

        return job

    def _dispatch_job(self, job_id: str) -> str:
        """
        Start download work without blocking the caller.

        When Celery is in ALWAYS_EAGER mode (no Redis), delay() would run the
        full download inside the HTTP request — the UI would never receive a
        job id until the file finished. In that case we use a daemon thread.
        """
        from apps.downloader.tasks import process_download

        eager = getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
        if eager:
            def _runner() -> None:
                close_old_connections()
                try:
                    DownloadService(self.repo).execute_download(job_id)
                except Exception:
                    logger.exception("Background download failed for %s", job_id)
                finally:
                    close_old_connections()

            thread = threading.Thread(
                target=_runner,
                name=f"vdl-download-{job_id[:8]}",
                daemon=True,
            )
            thread.start()
            return f"thread-{job_id}"

        async_result = process_download.delay(job_id)
        return async_result.id

    def create_bulk(
        self,
        urls: list[str],
        **kwargs: Any,
    ) -> list[DownloadJob]:
        jobs = []
        for url in urls:
            try:
                jobs.append(self.create_download(url, **kwargs))
            except DownloadServiceError as exc:
                logger.warning("Bulk skip %s: %s", url, exc)
        return jobs

    # ------------------------------------------------------------------
    # Lifecycle controls
    # ------------------------------------------------------------------
    def pause(self, job: DownloadJob) -> DownloadJob:
        if not job.can_pause:
            raise DownloadServiceError("Cannot pause this download", code="invalid_state")
        job.status = DownloadJob.Status.PAUSED
        job.stage = "paused"
        job.save(update_fields=["status", "stage", "updated_at"])
        # Best-effort: revoke celery if still queued
        if job.celery_task_id and job.status == DownloadJob.Status.PAUSED:
            from config.celery import app as celery_app

            celery_app.control.revoke(job.celery_task_id, terminate=False)
        broadcast_progress(job.id, job.to_progress_dict())
        return job

    def resume(self, job: DownloadJob) -> DownloadJob:
        if not job.can_resume:
            raise DownloadServiceError("Cannot resume this download", code="invalid_state")
        job.status = DownloadJob.Status.QUEUED
        job.stage = "queued"
        job.save(update_fields=["status", "stage", "updated_at"])
        task_id = self._dispatch_job(str(job.id))
        job.celery_task_id = task_id
        job.save(update_fields=["celery_task_id", "updated_at"])
        broadcast_progress(job.id, job.to_progress_dict())
        return job

    def cancel(self, job: DownloadJob) -> DownloadJob:
        if not job.can_cancel:
            raise DownloadServiceError("Cannot cancel this download", code="invalid_state")
        job.status = DownloadJob.Status.CANCELLED
        job.stage = "cancelled"
        job.save(update_fields=["status", "stage", "updated_at"])
        if job.celery_task_id:
            from config.celery import app as celery_app

            celery_app.control.revoke(job.celery_task_id, terminate=True)
        broadcast_progress(job.id, job.to_progress_dict())
        return job

    def retry(self, job: DownloadJob) -> DownloadJob:
        if job.status not in (DownloadJob.Status.FAILED, DownloadJob.Status.CANCELLED):
            raise DownloadServiceError("Only failed/cancelled jobs can be retried", code="invalid_state")
        job.status = DownloadJob.Status.QUEUED
        job.stage = "queued"
        job.progress = 0
        job.error_message = ""
        job.retry_count += 1
        job.save()
        task_id = self._dispatch_job(str(job.id))
        job.celery_task_id = task_id
        job.save(update_fields=["celery_task_id", "updated_at"])
        return job

    def redownload(self, job: DownloadJob) -> DownloadJob:
        """Create a new job from an existing one's options."""
        return self.create_download(
            job.url,
            user=job.user,
            session_key=job.session_key,
            mode=job.mode,
            quality=job.quality,
            audio_quality=job.audio_quality,
            output_format=job.output_format,
            audio_format=job.audio_format,
            selected_format_id=job.selected_format_id,
            subtitle_langs=job.subtitle_langs,
            embed_subs=job.embed_subs,
            embed_thumbnail=job.embed_thumbnail,
            embed_metadata=job.embed_metadata,
            check_duplicate=False,
            metadata={
                "title": job.title,
                "video_id": job.video_id,
                "platform": job.platform,
                "platform_display": job.platform_display,
                "thumbnail": job.thumbnail_url,
                "uploader": job.uploader,
                "duration": job.duration,
            },
        )

    # ------------------------------------------------------------------
    # Execution (called from Celery worker)
    # ------------------------------------------------------------------
    def execute_download(self, job_id: str | UUID) -> None:
        job = self.repo.get_by_id(job_id)
        if not job:
            logger.error("Job %s not found", job_id)
            return

        # Refresh and check cancel/pause
        job.refresh_from_db()
        if job.status in (DownloadJob.Status.CANCELLED, DownloadJob.Status.PAUSED):
            return

        job.status = DownloadJob.Status.DOWNLOADING
        job.stage = "downloading"
        job.progress = max(float(job.progress or 0), 0.0)
        job.started_at = timezone.now()
        job.save(
            update_fields=["status", "stage", "progress", "started_at", "updated_at"]
        )
        broadcast_progress(job.id, job.to_progress_dict())

        output_dir = Path(settings.DOWNLOAD_ROOT) / str(job.id)
        output_dir.mkdir(parents=True, exist_ok=True)

        last_flush = 0.0
        last_bytes = int(job.downloaded_bytes or 0)
        last_bytes_at = time.monotonic()
        pending: dict[str, Any] = {}

        def flush_progress(force: bool = False) -> None:
            nonlocal last_flush, pending
            if not pending and not force:
                return
            now = time.monotonic()
            if not force and (now - last_flush) < _PROGRESS_MIN_INTERVAL:
                return

            # Apply pending fields onto job instance
            for k, v in pending.items():
                setattr(job, k, v)
            pending = {}
            last_flush = now

            try:
                job.save(
                    update_fields=[
                        "progress",
                        "stage",
                        "speed_bps",
                        "eta_seconds",
                        "downloaded_bytes",
                        "total_bytes",
                        "updated_at",
                    ]
                )
            except Exception:
                logger.exception("Failed to save progress for %s", job.id)
            broadcast_progress(job.id, job.to_progress_dict())

        def on_progress(payload: dict[str, Any]) -> None:
            nonlocal last_bytes, last_bytes_at, pending
            job.refresh_from_db(fields=["status"])
            if job.status == DownloadJob.Status.CANCELLED:
                raise InterruptedError("cancelled")
            if job.status == DownloadJob.Status.PAUSED:
                raise InterruptedError("paused")

            # Merge payload without wiping fields that hooks omit
            if "stage" in payload and payload["stage"]:
                pending["stage"] = payload["stage"]
            if "progress" in payload and payload["progress"] is not None:
                # Never let progress go backwards (except tiny float noise)
                new_p = float(payload["progress"])
                cur = float(pending.get("progress", job.progress) or 0)
                pending["progress"] = max(cur, min(100.0, new_p))

            if "downloaded_bytes" in payload and payload["downloaded_bytes"] is not None:
                pending["downloaded_bytes"] = int(payload["downloaded_bytes"])
            if "total_bytes" in payload and payload["total_bytes"] is not None:
                pending["total_bytes"] = int(payload["total_bytes"])

            speed = payload.get("speed_bps")
            if speed is None or speed <= 0:
                # Estimate speed from byte delta when yt-dlp omits it
                dl = int(pending.get("downloaded_bytes", job.downloaded_bytes) or 0)
                now = time.monotonic()
                dt = now - last_bytes_at
                if dt > 0.2 and dl >= last_bytes:
                    speed = (dl - last_bytes) / dt
                last_bytes = dl
                last_bytes_at = now
            else:
                last_bytes = int(pending.get("downloaded_bytes", job.downloaded_bytes) or 0)
                last_bytes_at = time.monotonic()

            if speed is not None:
                pending["speed_bps"] = float(speed)

            if "eta_seconds" in payload and payload["eta_seconds"] is not None:
                pending["eta_seconds"] = int(payload["eta_seconds"])
            elif (
                speed
                and speed > 0
                and pending.get("total_bytes")
                and pending.get("downloaded_bytes") is not None
            ):
                remaining = int(pending["total_bytes"]) - int(pending["downloaded_bytes"])
                if remaining > 0:
                    pending["eta_seconds"] = int(remaining / speed)

            # Force immediate flush on terminal-ish stages so UI isn't stuck
            stage = str(pending.get("stage") or "")
            force = stage in {
                "finished",
                "processing",
                "finalizing",
                "error",
                "merging",
            } or float(pending.get("progress", 0) or 0) >= 99.0
            flush_progress(force=force)

        def cancel_check() -> bool:
            job.refresh_from_db(fields=["status"])
            return job.status in (
                DownloadJob.Status.CANCELLED,
                DownloadJob.Status.PAUSED,
            )

        engine = DownloadEngine(progress_callback=on_progress, cancel_check=cancel_check)

        try:
            noplaylist = job.mode not in (
                DownloadJob.Mode.PLAYLIST,
                DownloadJob.Mode.CHANNEL,
            )
            result = engine.download(
                job.url,
                output_dir,
                mode=job.mode,
                quality=job.quality,
                audio_quality=job.audio_quality,
                output_format=job.output_format,
                audio_format=job.audio_format,
                format_id=job.selected_format_id,
                bandwidth_limit_kbps=job.bandwidth_limit_kbps,
                subtitle_langs=job.subtitle_langs,
                embed_subs=job.embed_subs,
                embed_thumbnail=job.embed_thumbnail,
                embed_metadata=job.embed_metadata,
                write_description=job.write_description,
                write_thumbnail=job.write_thumbnail,
                playlist_start=job.playlist_start,
                playlist_end=job.playlist_end,
                noplaylist=noplaylist,
            )

            if not result.get("success"):
                raise DownloadServiceError(result.get("error") or "Download failed")

            # Final progress flush before complete
            flush_progress(force=True)

            job.mark_completed(result.get("filepath") or "", result.get("file_size"))
            job.file_hash = result.get("file_hash") or ""
            job.resolution = result.get("resolution") or ""
            job.vcodec = result.get("vcodec") or ""
            job.acodec = result.get("acodec") or ""
            job.fps = result.get("fps")
            job.progress = 100.0
            job.speed_bps = 0
            job.eta_seconds = 0
            job.stage = "completed"
            if result.get("file_size"):
                job.downloaded_bytes = result["file_size"]
                job.total_bytes = result["file_size"]
            if result.get("title") and not job.title:
                job.title = result["title"]
            job.save()

            self.repo.register_fingerprint(job)

            # Update user storage
            if job.user_id and job.file_size:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                User.objects.filter(pk=job.user_id).update(
                    storage_used_bytes=models_F_add(job.file_size)
                )

            broadcast_progress(job.id, job.to_progress_dict())
            if job.user_id:
                broadcast_user_event(
                    job.user_id,
                    "download_completed",
                    {"id": str(job.id), "title": job.title},
                )

            # Notification
            try:
                from services.notification_service import NotificationService

                NotificationService().notify_download_complete(job)
            except Exception:
                logger.exception("Notification failed")

            logger.info("Download completed: %s", job.id)

        except InterruptedError as exc:
            reason = str(exc)
            job.refresh_from_db()
            if "paused" in reason or job.status == DownloadJob.Status.PAUSED:
                job.status = DownloadJob.Status.PAUSED
                job.stage = "paused"
            else:
                job.status = DownloadJob.Status.CANCELLED
                job.stage = "cancelled"
            job.save(update_fields=["status", "stage", "updated_at"])
            broadcast_progress(job.id, job.to_progress_dict())

        except Exception as exc:
            logger.exception("Download failed for %s", job.id)
            job.mark_failed(str(exc))
            job.stage = "failed"
            job.save(update_fields=["stage", "updated_at"])
            broadcast_progress(job.id, job.to_progress_dict())
            if job.user_id:
                broadcast_user_event(
                    job.user_id,
                    "download_failed",
                    {"id": str(job.id), "title": job.title, "error": str(exc)[:200]},
                )
            # Retry?
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = DownloadJob.Status.QUEUED
                job.stage = "retrying"
                job.save(update_fields=["retry_count", "status", "stage", "updated_at"])
                # Delayed re-dispatch (thread sleep or celery countdown)
                delay = 30 * job.retry_count
                if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                    def _retry_later() -> None:
                        time.sleep(delay)
                        close_old_connections()
                        try:
                            self._dispatch_job(str(job.id))
                        finally:
                            close_old_connections()

                    threading.Thread(
                        target=_retry_later,
                        name=f"vdl-retry-{job.id}",
                        daemon=True,
                    ).start()
                else:
                    from apps.downloader.tasks import process_download

                    process_download.apply_async(
                        args=[str(job.id)], countdown=delay
                    )


def models_F_add(amount: int):
    from django.db.models import F

    return F("storage_used_bytes") + amount
