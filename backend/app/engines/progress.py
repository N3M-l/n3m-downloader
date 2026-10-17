"""Parsers for engine progress output."""

from __future__ import annotations

import re

UNITS = {
    "b": 1,
    "k": 1024,
    "kb": 1024,
    "kib": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "mib": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "gib": 1024**3,
    "t": 1024**4,
    "tb": 1024**4,
    "tib": 1024**4,
}
SIZE_RE = re.compile(r"([\d.]+)\s*([kmgt]?i?b)", re.IGNORECASE)
PERCENT_RE = re.compile(r"([\d.]+)\s*%")


def parse_percent(value: str | None) -> float | None:
    if not value:
        return None
    match = PERCENT_RE.search(value)
    if not match:
        return None
    try:
        return max(0.0, min(100.0, float(match.group(1))))
    except ValueError:
        return None


def parse_size(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    if not text or text.upper() in {"NA", "N/A", "UNKNOWN", "-"}:
        return None
    match = SIZE_RE.search(text)
    if not match:
        return None
    try:
        number = float(match.group(1))
    except ValueError:
        return None
    return number * UNITS.get(match.group(2).lower(), 1)


def parse_speed(value: str | None) -> float | None:
    return parse_size(value)


def parse_bytes(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip()
    if not text or text.upper() in {"NA", "N/A", "UNKNOWN", "-"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        pass
    size = parse_size(text)
    if size is None:
        return None
    return int(size)


def parse_eta(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip()
    if not text or text.upper() in {"NA", "N/A", "UNKNOWN", "-"}:
        return None
    parts = text.split(":")
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    if not numbers:
        return None
    seconds = 0
    for number in numbers:
        seconds = seconds * 60 + number
    return max(0, seconds)
