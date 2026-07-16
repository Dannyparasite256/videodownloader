from utils.format_utils import format_bytes, format_duration, format_eta, resolution_label


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert "KB" in format_bytes(2048)
    assert format_bytes(None) == "—"


def test_format_duration():
    assert format_duration(65) == "1:05"
    assert format_duration(3661) == "1:01:01"
    assert format_duration(None) == "—"


def test_format_eta():
    assert format_eta(30) == "30s"
    assert "m" in format_eta(90)


def test_resolution_label():
    assert resolution_label(1080) == "1080p"
    assert resolution_label(2160) == "4K"
    assert resolution_label(None) == "Unknown"
