"""
High-performance yt-dlp download engine.

Features:
- Metadata extraction with format enumeration
- Progress hooks → WebSocket/DB updates
- Resume, retry, rate limiting
- FFmpeg merge / convert hooks
- Integrity-friendly post-processing
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from django.conf import settings

from utils.format_utils import resolution_label
from utils.url_utils import detect_platform, sanitize_filename

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass
class FormatInfo:
    format_id: str
    ext: str
    resolution: str
    height: Optional[int] = None
    width: Optional[int] = None
    fps: Optional[float] = None
    vcodec: str = "none"
    acodec: str = "none"
    filesize: Optional[int] = None
    tbr: Optional[float] = None
    abr: Optional[float] = None
    format_note: str = ""
    is_video: bool = False
    is_audio: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_id": self.format_id,
            "ext": self.ext,
            "resolution": self.resolution,
            "height": self.height,
            "width": self.width,
            "fps": self.fps,
            "vcodec": self.vcodec,
            "acodec": self.acodec,
            "filesize": self.filesize,
            "tbr": self.tbr,
            "abr": self.abr,
            "format_note": self.format_note,
            "is_video": self.is_video,
            "is_audio": self.is_audio,
        }


@dataclass
class VideoMetadata:
    url: str
    title: str = ""
    description: str = ""
    uploader: str = ""
    uploader_id: str = ""
    thumbnail: str = ""
    duration: Optional[int] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    upload_date: Optional[str] = None
    webpage_url: str = ""
    video_id: str = ""
    extractor: str = ""
    platform: str = ""
    platform_display: str = ""
    is_live: bool = False
    is_playlist: bool = False
    playlist_count: Optional[int] = None
    chapters: list[dict] = field(default_factory=list)
    subtitles: list[str] = field(default_factory=list)
    formats: list[FormatInfo] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description[:2000] if self.description else "",
            "uploader": self.uploader,
            "uploader_id": self.uploader_id,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "upload_date": self.upload_date,
            "webpage_url": self.webpage_url,
            "video_id": self.video_id,
            "extractor": self.extractor,
            "platform": self.platform,
            "platform_display": self.platform_display,
            "is_live": self.is_live,
            "is_playlist": self.is_playlist,
            "playlist_count": self.playlist_count,
            "chapters": self.chapters,
            "subtitles": self.subtitles,
            "formats": [f.to_dict() for f in self.formats],
        }


class DownloadEngine:
    """
    Thin, testable wrapper around yt-dlp.

    Does not write Django models directly — callers (services/tasks) own persistence.
    """

    def __init__(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.progress_callback = progress_callback
        self.cancel_check = cancel_check
        self._last_progress: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    def extract_metadata(self, url: str, *, process_playlist: bool = False) -> VideoMetadata:
        """Fetch metadata and available formats without downloading."""
        import yt_dlp

        platform = detect_platform(url)
        base = self._base_opts()
        attempts: list[dict[str, Any]] = [
            {
                **base,
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": "in_playlist" if process_playlist else False,
                "noplaylist": not process_playlist,
            }
        ]
        # Fallback: if we have cookies, also try pure web client only
        if base.get("cookiefile"):
            web_only = dict(attempts[0])
            web_only["extractor_args"] = {"youtube": {"player_client": ["web", "mweb"]}}
            attempts.append(web_only)

        info = None
        last_exc: BaseException | None = None
        for ydl_opts in attempts:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                if info is not None:
                    break
            except Exception as exc:
                last_exc = exc
                logger.warning("extract_metadata attempt failed: %s", exc)
                continue

        # Stale/invalid cookies often make cloud bot checks worse — retry without them
        if info is None and last_exc and base.get("cookiefile"):
            low = str(last_exc).lower()
            if "sign in to confirm" in low or "not a bot" in low:
                bare = dict(attempts[0])
                bare.pop("cookiefile", None)
                bare["extractor_args"] = {
                    "youtube": {"player_client": ["android", "ios", "tv_embedded", "mweb"]}
                }
                try:
                    with yt_dlp.YoutubeDL(bare) as ydl:
                        info = ydl.extract_info(url, download=False)
                    if info is not None:
                        logger.info("extract_metadata succeeded without cookies (fallback)")
                except Exception as exc:
                    last_exc = exc
                    logger.warning("extract_metadata cookie-less fallback failed: %s", exc)

        if info is None:
            if last_exc:
                raise last_exc
            raise ValueError("Could not extract metadata from URL")

        # Playlist root
        if info.get("_type") == "playlist" or (info.get("entries") and not info.get("id")):
            entries = list(info.get("entries") or [])
            first = next((e for e in entries if e), None) or {}
            return VideoMetadata(
                url=url,
                title=info.get("title") or "Playlist",
                uploader=info.get("uploader") or info.get("channel") or "",
                thumbnail=info.get("thumbnail") or first.get("thumbnail") or "",
                video_id=str(info.get("id") or ""),
                extractor=info.get("extractor") or info.get("ie_key") or "",
                platform=platform.slug,
                platform_display=platform.display_name,
                is_playlist=True,
                playlist_count=info.get("playlist_count") or len(entries),
                webpage_url=info.get("webpage_url") or url,
                raw={"playlist_title": info.get("title"), "entry_count": len(entries)},
            )

        return self._parse_info(url, info, platform)

    def _parse_info(self, url: str, info: dict, platform) -> VideoMetadata:
        formats = self._parse_formats(info.get("formats") or [])
        subs = list((info.get("subtitles") or {}).keys()) + list(
            (info.get("automatic_captions") or {}).keys()
        )
        upload_date = info.get("upload_date")  # YYYYMMDD
        if upload_date and len(str(upload_date)) == 8:
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        else:
            upload_date = None

        chapters = [
            {
                "start_time": c.get("start_time"),
                "end_time": c.get("end_time"),
                "title": c.get("title"),
            }
            for c in (info.get("chapters") or [])
        ]

        thumbs = info.get("thumbnails") or []
        thumbnail = info.get("thumbnail") or (thumbs[-1]["url"] if thumbs else "")

        return VideoMetadata(
            url=url,
            title=info.get("title") or "Untitled",
            description=info.get("description") or "",
            uploader=info.get("uploader") or info.get("channel") or info.get("creator") or "",
            uploader_id=str(info.get("uploader_id") or info.get("channel_id") or ""),
            thumbnail=thumbnail,
            duration=info.get("duration"),
            view_count=info.get("view_count"),
            like_count=info.get("like_count"),
            upload_date=upload_date,
            webpage_url=info.get("webpage_url") or url,
            video_id=str(info.get("id") or ""),
            extractor=info.get("extractor") or info.get("ie_key") or "",
            platform=platform.slug,
            platform_display=platform.display_name,
            is_live=bool(info.get("is_live")),
            is_playlist=False,
            chapters=chapters,
            subtitles=sorted(set(subs)),
            formats=formats,
            raw={
                k: info.get(k)
                for k in (
                    "categories",
                    "tags",
                    "age_limit",
                    "availability",
                    "live_status",
                )
                if info.get(k) is not None
            },
        )

    def _parse_formats(self, formats: list[dict]) -> list[FormatInfo]:
        result: list[FormatInfo] = []
        seen: set[str] = set()
        for f in formats:
            fid = str(f.get("format_id") or "")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            vcodec = f.get("vcodec") or "none"
            acodec = f.get("acodec") or "none"
            height = f.get("height")
            width = f.get("width")
            is_video = vcodec != "none"
            is_audio = acodec != "none"
            res = resolution_label(height) if height else (
                "audio" if is_audio and not is_video else (f.get("format_note") or "unknown")
            )
            result.append(
                FormatInfo(
                    format_id=fid,
                    ext=f.get("ext") or "unknown",
                    resolution=res,
                    height=height,
                    width=width,
                    fps=f.get("fps"),
                    vcodec=vcodec,
                    acodec=acodec,
                    filesize=f.get("filesize") or f.get("filesize_approx"),
                    tbr=f.get("tbr"),
                    abr=f.get("abr"),
                    format_note=f.get("format_note") or "",
                    is_video=is_video,
                    is_audio=is_audio,
                )
            )
        # Prefer higher quality first
        result.sort(key=lambda x: (x.height or 0, x.tbr or 0), reverse=True)
        return result

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def download(
        self,
        url: str,
        output_dir: Path,
        *,
        mode: str = "video_audio",
        quality: str = "best",
        audio_quality: str = "192",
        output_format: str = "mp4",
        audio_format: str = "mp3",
        format_id: str = "",
        filename_template: str = "%(title).180B [%(id)s].%(ext)s",
        bandwidth_limit_kbps: int = 0,
        subtitle_langs: Optional[list[str]] = None,
        embed_subs: bool = False,
        embed_thumbnail: bool = True,
        embed_metadata: bool = True,
        write_description: bool = False,
        write_thumbnail: bool = False,
        playlist_start: Optional[int] = None,
        playlist_end: Optional[int] = None,
        noplaylist: bool = True,
    ) -> dict[str, Any]:
        """
        Download media to *output_dir*. Returns result dict with paths and media info.

        Raises on permanent failure. Respects cancel_check between progress hooks.
        """
        import yt_dlp

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ydl_opts = self._base_opts()
        outtmpl = str(output_dir / filename_template)
        ydl_opts.update(
            {
                "outtmpl": outtmpl,
                "progress_hooks": [self._progress_hook],
                "postprocessor_hooks": [self._postprocessor_hook],
                "noplaylist": noplaylist,
                "continuedl": True,
                "overwrites": False,
                # Ensure progress hooks fire even when quiet
                "noprogress": False,
            }
        )

        if bandwidth_limit_kbps and bandwidth_limit_kbps > 0:
            ydl_opts["ratelimit"] = bandwidth_limit_kbps * 1024

        if playlist_start:
            ydl_opts["playliststart"] = playlist_start
        if playlist_end:
            ydl_opts["playlistend"] = playlist_end

        ydl_opts["format"] = self._build_format_string(mode, quality, format_id)
        ydl_opts["postprocessors"] = self._build_postprocessors(
            mode=mode,
            output_format=output_format,
            audio_format=audio_format,
            audio_quality=audio_quality,
            embed_subs=embed_subs,
            embed_thumbnail=embed_thumbnail,
            embed_metadata=embed_metadata,
        )

        if write_thumbnail or mode == "thumbnail":
            ydl_opts["writethumbnail"] = True
        if write_description or mode == "metadata":
            ydl_opts["writedescription"] = True
            ydl_opts["writeinfojson"] = True
        if subtitle_langs:
            ydl_opts["writesubtitles"] = True
            ydl_opts["subtitleslangs"] = subtitle_langs
        if mode == "subtitles":
            ydl_opts["skip_download"] = True
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True
            ydl_opts["subtitleslangs"] = subtitle_langs or ["en", "all"]

        if mode == "thumbnail":
            ydl_opts["skip_download"] = True
            ydl_opts["writethumbnail"] = True

        logger.info("Starting download", extra={"url": url, "mode": mode, "quality": quality})

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        if self.cancel_check and self.cancel_check():
            raise InterruptedError("Download cancelled")

        return self._build_result(info, output_dir)

    def _build_format_string(self, mode: str, quality: str, format_id: str) -> str:
        if format_id:
            return format_id

        if mode == "audio_only":
            return "bestaudio/best"

        if mode == "video_only":
            if quality in ("best", "highest"):
                return "bestvideo/best"
            if quality in ("worst", "lowest"):
                return "worstvideo/worst"
            if quality.isdigit():
                return f"bestvideo[height<={quality}]/bestvideo/best"
            return "bestvideo/best"

        # video_audio (default)
        if quality in ("best", "highest", "original"):
            return "bv*+ba/b"
        if quality in ("worst", "lowest"):
            return "wv*+wa/w"
        if quality.isdigit():
            h = quality
            return (
                f"bv*[height<={h}]+ba/b[height<={h}]/"
                f"bv*+ba/b"
            )
        return "bv*+ba/b"

    def _build_postprocessors(
        self,
        *,
        mode: str,
        output_format: str,
        audio_format: str,
        audio_quality: str,
        embed_subs: bool,
        embed_thumbnail: bool,
        embed_metadata: bool,
    ) -> list[dict]:
        pps: list[dict] = []

        if mode == "audio_only":
            preferred = audio_format if audio_format != "best" else "mp3"
            q = audio_quality if audio_quality not in ("best", "lossless") else "0"
            pps.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": preferred,
                    "preferredquality": q,
                }
            )
        elif mode in ("video_audio", "video_only") and output_format:
            # Merge to container when needed
            if output_format in ("mp4", "mkv", "webm", "mov", "avi"):
                pps.append({"key": "FFmpegVideoConvertor", "preferedformat": output_format})

        if embed_metadata:
            pps.append({"key": "FFmpegMetadata", "add_metadata": True})
        if embed_thumbnail and mode != "audio_only":
            pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
        elif embed_thumbnail and mode == "audio_only":
            pps.append({"key": "EmbedThumbnail"})
        if embed_subs:
            pps.append({"key": "FFmpegEmbedSubtitle"})

        return pps

    def _progress_hook(self, d: dict[str, Any]) -> None:
        if self.cancel_check and self.cancel_check():
            raise InterruptedError("Download cancelled by user")

        status = d.get("status")
        payload: dict[str, Any] = {"stage": status or "downloading"}

        if status == "downloading":
            downloaded = int(d.get("downloaded_bytes") or 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total is not None:
                try:
                    total = int(total)
                except (TypeError, ValueError):
                    total = None
            if total is not None and total <= 0:
                total = None

            speed = d.get("speed")
            try:
                speed = float(speed) if speed is not None else None
            except (TypeError, ValueError):
                speed = None
            if speed is not None and speed < 0:
                speed = None

            eta = d.get("eta")
            try:
                eta = int(eta) if eta is not None else None
            except (TypeError, ValueError):
                eta = None

            # Prefer explicit percent from yt-dlp, then bytes ratio
            pct = self._extract_percent(d, downloaded, total)

            # Fragment progress fallback (HLS / DASH)
            if pct <= 0 and d.get("fragment_index") and d.get("fragment_count"):
                try:
                    fi = int(d["fragment_index"])
                    fc = int(d["fragment_count"])
                    if fc > 0:
                        pct = min(99.0, (fi / fc) * 100.0)
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

            payload.update(
                {
                    "progress": pct,
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "speed_bps": speed,
                    "eta_seconds": eta,
                    "filename": d.get("filename") or d.get("info_dict", {}).get("filename"),
                }
            )
        elif status == "finished":
            # One stream finished — may still merge/post-process
            downloaded = int(d.get("downloaded_bytes") or d.get("total_bytes") or 0)
            payload.update(
                {
                    "progress": 99.0,
                    "stage": "processing",
                    "downloaded_bytes": downloaded,
                    "total_bytes": downloaded or None,
                    "speed_bps": 0,
                    "eta_seconds": 0,
                    "filename": d.get("filename"),
                }
            )
        elif status == "error":
            payload["stage"] = "error"

        self._last_progress = payload
        if self.progress_callback:
            try:
                self.progress_callback(payload)
            except InterruptedError:
                raise
            except Exception:
                logger.exception("Progress callback failed")

    @staticmethod
    def _extract_percent(d: dict[str, Any], downloaded: int, total: Optional[int]) -> float:
        """Best-effort percent from yt-dlp progress dict."""
        # Native float if present (some versions)
        for key in ("_percent", "percent"):
            raw = d.get(key)
            if raw is not None:
                try:
                    return max(0.0, min(100.0, float(raw)))
                except (TypeError, ValueError):
                    pass

        pct_str = d.get("_percent_str") or d.get("percent_str") or ""
        if pct_str and "n/a" not in str(pct_str).lower():
            m = re.search(r"([\d.]+)", str(pct_str).replace(",", "."))
            if m:
                try:
                    return max(0.0, min(100.0, float(m.group(1))))
                except ValueError:
                    pass

        if total and total > 0 and downloaded >= 0:
            return max(0.0, min(100.0, (downloaded / total) * 100.0))

        return 0.0

    def _postprocessor_hook(self, d: dict[str, Any]) -> None:
        status = d.get("status")
        if status == "started":
            stage = d.get("postprocessor") or "processing"
            if self.progress_callback:
                self.progress_callback(
                    {
                        "stage": str(stage).lower(),
                        "progress": 99.0,
                        "speed_bps": 0,
                        "eta_seconds": 0,
                    }
                )
        elif status == "finished":
            if self.progress_callback:
                self.progress_callback(
                    {
                        "stage": "finalizing",
                        "progress": 99.5,
                        "speed_bps": 0,
                        "eta_seconds": 0,
                    }
                )

    def _build_result(self, info: Optional[dict], output_dir: Path) -> dict[str, Any]:
        if not info:
            return {"success": False, "error": "No info returned"}

        # Prefer requested downloads list
        filepath = None
        if info.get("requested_downloads"):
            filepath = info["requested_downloads"][0].get("filepath")
        if not filepath:
            filepath = info.get("filepath") or info.get("_filename")

        # Fallback: newest file in output dir
        if not filepath or not Path(filepath).exists():
            files = sorted(output_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
            media_exts = {
                ".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".3gp",
                ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus",
                ".vtt", ".srt", ".jpg", ".png", ".webp",
            }
            for f in files:
                if f.suffix.lower() in media_exts and not f.name.endswith(".part"):
                    filepath = str(f)
                    break

        file_size = None
        file_hash = ""
        if filepath and Path(filepath).exists():
            file_size = Path(filepath).stat().st_size
            file_hash = self._sha256_file(Path(filepath))

        return {
            "success": True,
            "filepath": filepath or "",
            "file_size": file_size,
            "file_hash": file_hash,
            "title": info.get("title") or "",
            "ext": info.get("ext") or (Path(filepath).suffix.lstrip(".") if filepath else ""),
            "resolution": resolution_label(info.get("height")),
            "vcodec": info.get("vcodec") or "",
            "acodec": info.get("acodec") or "",
            "fps": info.get("fps"),
            "duration": info.get("duration"),
            "video_id": str(info.get("id") or ""),
            "extractor": info.get("extractor") or "",
        }

    @staticmethod
    def _sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while True:
                    block = f.read(chunk)
                    if not block:
                        break
                    h.update(block)
            return h.hexdigest()
        except OSError:
            return ""

    def _base_opts(self) -> dict[str, Any]:
        # Resolve cookies FIRST — client choice depends on whether we have them.
        resolved = self._resolve_cookiefile()
        free = getattr(settings, "RENDER_FREE_TIER", False)

        # With cookies: prefer "web" so the logged-in session is actually used.
        # Without cookies: mobile/TV clients (often better for anonymous, still often
        # blocked on datacenter IPs for YouTube).
        if resolved:
            player_clients = ["web", "web_safari", "mweb", "android", "ios"]
        elif free:
            player_clients = ["android", "ios", "mweb", "tv_embedded"]
        else:
            player_clients = ["android", "ios", "tv_embedded", "mweb", "web"]

        opts: dict[str, Any] = {
            "socket_timeout": getattr(settings, "YTDLP_SOCKET_TIMEOUT", 30),
            "retries": getattr(settings, "YTDLP_RETRIES", 3),
            "fragment_retries": 10,
            "ignoreerrors": False,
            "no_color": True,
            "geo_bypass": True,
            "quiet": True,
            "no_warnings": True,
            # Legal: do not bypass DRM
            "allow_unplayable_formats": False,
            # Prefer ffmpeg for merge
            "merge_output_format": "mp4",
            "extractor_args": {
                "youtube": {
                    "player_client": player_clients,
                }
            },
            # YouTube n/sig challenges need a real JS runtime (deno preferred, node fallback)
            "js_runtimes": {"deno": {}, "node": {}},
            # Allow fetching EJS solver scripts when yt-dlp-ejs needs updates
            "remote_components": ["ejs:github"],
            # Free Render OOM protection: fewer parallel fragment downloads
            "concurrent_fragment_downloads": 1 if free else 4,
            "http_headers": {
                "User-Agent": getattr(
                    settings,
                    "YTDLP_USER_AGENT",
                    (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        if resolved:
            opts["cookiefile"] = str(resolved)
            logger.info(
                "yt-dlp using cookies file %s (%s bytes) clients=%s",
                resolved,
                resolved.stat().st_size,
                player_clients,
            )
        else:
            logger.warning("yt-dlp: no YouTube cookies file — cloud YouTube likely fails")

        # Local/dev only: pull cookies from an installed browser profile
        browser = getattr(settings, "YTDLP_COOKIES_FROM_BROWSER", "") or ""
        if browser and "cookiefile" not in opts:
            parts = browser.split(":", 1)
            if len(parts) == 2:
                opts["cookiesfrombrowser"] = (parts[0].strip(), parts[1].strip(), None, None)
            else:
                opts["cookiesfrombrowser"] = (parts[0].strip(), None, None, None)
            logger.info("yt-dlp using cookies from browser: %s", browser)

        return opts

    @staticmethod
    def _resolve_cookiefile() -> Path | None:
        """Find or materialize a Netscape cookies.txt for yt-dlp."""
        import base64

        cookiefile = getattr(settings, "YTDLP_COOKIES_FILE", "") or ""
        base = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        candidates = []
        if cookiefile:
            candidates.append(Path(cookiefile))
        candidates.extend(
            [
                base / "secrets" / "cookies.txt",
                base / "secrets" / "cookies.from_env.txt",
                base / "cookies.txt",
            ]
        )
        resolved = next((p for p in candidates if p.is_file() and p.stat().st_size > 32), None)
        if resolved:
            return resolved

        # Re-hydrate from env (survives free Render sleep) or DB (survives restarts while disk lives)
        b64 = (getattr(settings, "YTDLP_COOKIES_BASE64", "") or os.environ.get("YTDLP_COOKIES_BASE64", "")).strip()
        if not b64:
            try:
                from apps.accounts.models import SiteSecret

                b64 = (SiteSecret.get_value("youtube_cookies_b64") or "").strip()
            except Exception:
                b64 = ""
        if not b64:
            return None
        try:
            raw = base64.b64decode(b64)
        except Exception:
            try:
                raw = base64.urlsafe_b64decode(b64 + "==")
            except Exception:
                logger.warning("Cookie base64 is not valid")
                return None
        if len(raw) < 32:
            return None
        secrets_dir = base / "secrets"
        try:
            secrets_dir.mkdir(parents=True, exist_ok=True)
            dest = secrets_dir / "cookies.txt"
            dest.write_bytes(raw)
            try:
                dest.chmod(0o600)
            except OSError:
                pass
            logger.info("Wrote cookies from env/DB (%s bytes)", len(raw))
            return dest
        except OSError as exc:
            logger.warning("Could not write cookies file: %s", exc)
            return None


def ensure_ffmpeg() -> bool:
    """Return True if ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def humanize_ytdlp_error(exc: BaseException) -> str:
    """Map common yt-dlp errors to user-facing guidance."""
    msg = str(exc)
    low = msg.lower()
    if "no longer valid" in low or "cookies are no longer valid" in low:
        return (
            "Your YouTube cookies expired (browser rotated the session). "
            "Log into YouTube in Chrome again → re-export a FRESH cookies.txt "
            "(extension “Get cookies.txt LOCALLY” on youtube.com) → Settings → "
            "Upload cookies. On Render also update YTDLP_COOKIES_BASE64 and redeploy."
        )
    if (
        "sign in to confirm" in low
        or "not a bot" in low
        or "cookies-from-browser" in low
        or "failed to decrypt with dpapi" in low
    ):
        return (
            "YouTube is blocking this cloud server (bot check). "
            "Cookies on the server are missing, incomplete, or expired. "
            "Fix: log into YouTube in Chrome → export a FRESH Netscape cookies.txt "
            "(must include LOGIN_INFO and SID) → Settings → YouTube cookies → Upload, "
            "then set YTDLP_COOKIES_BASE64 on Render and redeploy. "
            "If it still fails, use the home PC app (residential IP) — cloud IPs are often blocked."
        )
    if "no video formats found" in low or "formats may be missing" in low:
        return (
            "YouTube returned no playable formats (JS challenge / player update). "
            "The server needs Deno/Node for yt-dlp. Redeploy the latest image, or try again later."
        )
    if "private video" in low or "login required" in low:
        return "This video is private or requires login. It cannot be downloaded without permission."
    if "video unavailable" in low:
        return "This video is unavailable (removed, region-locked, or restricted)."
    if "unsupported url" in low:
        return "This site or URL is not supported."
    # Trim noisy prefixes
    cleaned = re.sub(r"^ERROR:\s*", "", msg).strip()
    if len(cleaned) > 400:
        cleaned = cleaned[:400] + "…"
    return cleaned or "Could not fetch video information."
