from __future__ import annotations

from app.engines.progress import parse_bytes, parse_eta, parse_percent, parse_speed


def test_parse_percent():
    assert parse_percent(" 42.5%") == 42.5
    assert parse_percent("NA") is None
    assert parse_percent(None) is None


def test_parse_speed_units():
    assert parse_speed("1.5MiB/s") == 1.5 * 1024**2
    assert parse_speed("800KiB/s") == 800 * 1024
    assert parse_speed("2.0MB/s") == 2 * 1024**2
    assert parse_speed("NA") is None


def test_parse_eta():
    assert parse_eta("00:15") == 15
    assert parse_eta("01:02:03") == 3723
    assert parse_eta("NA") is None


def test_parse_bytes():
    assert parse_bytes("1024") == 1024
    assert parse_bytes("1.0MiB") == 1024**2
    assert parse_bytes("NA") is None
