"""Unit tests for format string builder (no network)."""
from apps.downloader.engine import DownloadEngine


def test_format_best():
    eng = DownloadEngine()
    assert "bv" in eng._build_format_string("video_audio", "best", "")


def test_format_height():
    eng = DownloadEngine()
    s = eng._build_format_string("video_audio", "720", "")
    assert "720" in s


def test_format_audio():
    eng = DownloadEngine()
    assert eng._build_format_string("audio_only", "best", "") == "bestaudio/best"


def test_format_id_override():
    eng = DownloadEngine()
    assert eng._build_format_string("video_audio", "best", "22") == "22"
