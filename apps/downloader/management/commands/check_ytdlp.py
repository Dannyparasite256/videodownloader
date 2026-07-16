"""Verify yt-dlp + cookie configuration against a sample URL."""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.downloader.engine import DownloadEngine, humanize_ytdlp_error


class Command(BaseCommand):
    help = "Test yt-dlp YouTube access and show which cookie source is active"

    def add_arguments(self, parser):
        parser.add_argument(
            "url",
            nargs="?",
            default="https://www.youtube.com/watch?v=jNQXAC9IVRw",
            help="Video URL to probe (default: short public YouTube video)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Cookie configuration:")
        self.stdout.write(f"  YTDLP_COOKIES_FILE          = {settings.YTDLP_COOKIES_FILE or '(empty)'}")
        self.stdout.write(
            f"  YTDLP_COOKIES_FROM_BROWSER  = {settings.YTDLP_COOKIES_FROM_BROWSER or '(empty)'}"
        )
        self.stdout.write(
            f"  YTDLP_COOKIES_BASE64 set    = {bool(getattr(settings, 'YTDLP_COOKIES_BASE64', ''))}"
        )

        url = options["url"]
        self.stdout.write(f"\nProbing: {url}\n")
        engine = DownloadEngine()
        opts = engine._base_opts()
        self.stdout.write(f"  Active cookiefile          = {opts.get('cookiefile', '(none)')}")
        self.stdout.write(f"  Active cookiesfrombrowser  = {opts.get('cookiesfrombrowser', '(none)')}")

        try:
            meta = engine.extract_metadata(url)
            self.stdout.write(self.style.SUCCESS(f"\nOK — {meta.title}"))
            self.stdout.write(f"  uploader = {meta.uploader}")
            self.stdout.write(f"  duration = {meta.duration}s")
            self.stdout.write(f"  formats  = {len(meta.formats)}")
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"\nFAILED — {humanize_ytdlp_error(exc)}"))
            self.stdout.write(self.style.WARNING(f"Raw: {exc}"))
            self.stdout.write(
                "\nSee docs/YOUTUBE_COOKIES.md — export cookies.txt into secrets/cookies.txt "
                "or set YTDLP_COOKIES_BASE64 on Render."
            )
