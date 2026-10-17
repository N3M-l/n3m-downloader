"""Filesystem helpers: safe names, disk quota, cleanup, zip output."""

from __future__ import annotations

import re
import shutil
import time
import unicodedata
import zipfile
from pathlib import Path

INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
WHITESPACE = re.compile(r"\s+")
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
TEMP_SUFFIXES = {".part", ".ytdl", ".tmp", ".download", ".crdownload"}


def safe_filename(name: str, fallback: str = "n3m-download", max_length: int = 120) -> str:
    value = unicodedata.normalize("NFKC", name or "").strip()
    value = INVALID_CHARS.sub("_", value)
    value = WHITESPACE.sub(" ", value).strip(" ._")
    if not value:
        return fallback
    stem = value.rsplit(".", 1)[0].strip(" ._") or fallback
    if stem.upper() in WINDOWS_RESERVED:
        stem = f"_{stem}"
    value = stem if "." not in value else f"{stem}.{value.rsplit('.', 1)[1]}"
    if len(value) > max_length:
        if "." in value:
            base, ext = value.rsplit(".", 1)
            value = f"{base[: max_length - len(ext) - 1]}.{ext}"
        else:
            value = value[:max_length]
    return value or fallback


def ensure_extension(name: str, extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if not ext:
        return name
    if name.lower().endswith("." + ext):
        return name
    return f"{name}.{ext}"


def directory_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def disk_status(work_dir: Path, min_free_gb: float) -> dict[str, float | bool]:
    usage = shutil.disk_usage(work_dir)
    free_gb = usage.free / (1024**3)
    total_gb = usage.total / (1024**3)
    return {
        "freeGb": round(free_gb, 2),
        "totalGb": round(total_gb, 2),
        "minFreeGb": round(min_free_gb, 2),
        "ok": free_gb >= min_free_gb,
    }


def has_quota(work_dir: Path, min_free_gb: float, incoming_bytes: int = 0) -> bool:
    usage = shutil.disk_usage(work_dir)
    required = incoming_bytes + int(min_free_gb * 1024**3)
    return usage.free >= required


def pick_output(directory: Path) -> Path | None:
    candidates: list[Path] = []
    try:
        for item in directory.rglob("*"):
            if not item.is_file():
                continue
            if item.suffix.lower() in TEMP_SUFFIXES:
                continue
            if item.name.endswith(".zip") and item.parent == directory and any(
                other.parent != directory for other in directory.rglob("*") if other.is_file()
            ):
                continue
            candidates.append(item)
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_size)


def cleanup_old_jobs(jobs_dir: Path, retention_minutes: int) -> dict[str, int]:
    """Delete job directories older than the retention window."""
    freed = 0
    removed = 0
    if not jobs_dir.exists():
        return {"freedBytes": 0, "removedJobs": 0}
    cutoff = time.time() - retention_minutes * 60
    for entry in jobs_dir.iterdir():
        try:
            if not entry.is_dir() or entry.stat().st_mtime > cutoff:
                continue
            freed += directory_size(entry)
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
        except OSError:
            continue
    return {"freedBytes": freed, "removedJobs": removed}


def cleanup_tmp(tmp_dir: Path) -> dict[str, int]:
    """Remove everything inside the scratch directory."""
    freed = 0
    removed = 0
    if not tmp_dir.exists():
        return {"freedBytes": 0, "removedFiles": 0}
    for item in tmp_dir.iterdir():
        try:
            size = directory_size(item) if item.is_dir() else item.stat().st_size
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            freed += size
            removed += 1
        except OSError:
            continue
    return {"freedBytes": freed, "removedFiles": removed}


def zip_directory(source: Path, destination: Path) -> tuple[int, int]:
    """Zip every file under source; return (file count, uncompressed bytes)."""
    count = 0
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(source.rglob("*")):
            if not item.is_file() or item == destination:
                continue
            archive.write(item, arcname=item.relative_to(source))
            count += 1
            size += item.stat().st_size
    return count, size
