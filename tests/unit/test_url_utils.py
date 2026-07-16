"""Unit tests for URL utilities."""
from utils.url_utils import (
    detect_platform,
    extract_urls_from_text,
    is_valid_url,
    sanitize_filename,
)


def test_is_valid_url():
    assert is_valid_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_valid_url("http://localhost:8000/x")
    assert not is_valid_url("")
    assert not is_valid_url("not-a-url")
    assert not is_valid_url("ftp://example.com/file")


def test_detect_platform_youtube():
    info = detect_platform("https://www.youtube.com/watch?v=abc")
    assert info.slug == "youtube"
    assert info.is_known


def test_detect_platform_x():
    info = detect_platform("https://x.com/user/status/123")
    assert info.slug == "twitter"


def test_detect_platform_unknown():
    info = detect_platform("https://example.com/video/1")
    assert info.slug == "example"
    assert not info.is_known


def test_sanitize_filename():
    assert ".." not in sanitize_filename('a<>:"/\\|?*b')
    assert sanitize_filename("") == "download"
    assert len(sanitize_filename("x" * 500)) <= 180


def test_extract_urls():
    text = "see https://youtu.be/abc and https://tiktok.com/@x/video/1 end"
    urls = extract_urls_from_text(text)
    assert len(urls) == 2
