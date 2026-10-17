"""gallery-dl engine: image albums downloaded and packed as one ZIP."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path

from ..config import Settings
from ..errors import EngineError
from ..jobs import Job
from ..storage import safe_filename, zip_directory
from .base import module_available, package_version, run_process, tail

LOGGER = logging.getLogger("n3m.gallerydl")


class GalleryDlEngine:
    key = "gallerydl"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def command(self) -> list[str]:
        configured = self.settings.gallerydl_path
        if configured:
            return [configured]
        executable = shutil.which("gallery-dl")
        if executable:
            return [executable]
        return [sys.executable, "-m", "gallery_dl"]

    def available(self) -> bool:
        if self.settings.gallerydl_path:
            return Path(self.settings.gallerydl_path).exists() or bool(
                shutil.which(self.settings.gallerydl_path)
            )
        return bool(shutil.which("gallery-dl")) or module_available("gallery_dl")

    def version(self) -> str | None:
        return package_version("gallery-dl")

    async def inspect(self, url: str) -> dict:
        if not self.available():
            raise EngineError(
                "engine_unavailable",
                "محرّك gallery-dl غير مثبّت على الخادم. راجع دليل التشغيل.",
            )
        command = self.command() + ["--dump-json", "--no-download", url]
        code, stdout, stderr = await run_process(command, timeout=75)
        if code != 0:
            raise EngineError(
                "inspect_failed",
                "تعذّر قراءة هذا الألبوم. تأكد أن الحساب أو المعرض عام.",
                tail(stderr),
            )
        items = self._parse_items(stdout)
        if not items:
            raise EngineError("inspect_failed", "لم يعثر المحرك على صور في هذا الرابط.")
        first = items[0]
        title = (
            first.get("title")
            or first.get("album")
            or first.get("category")
            or "ألبوم صور N3M"
        )
        return {
            "title": str(title)[:300],
            "uploader": str(first.get("username") or first.get("user") or "") or None,
            "durationSeconds": None,
            "thumbnail": None,
            "filesizeBytes": None,
            "formats": [
                {
                    "id": "zip",
                    "label": f"ZIP — {len(items)} عنصرًا",
                    "ext": "zip",
                    "height": None,
                    "audioBitrate": None,
                    "sizeBytes": None,
                }
            ],
            "kind": "images",
            "itemCount": len(items),
        }

    def _parse_items(self, stdout: bytes) -> list[dict]:
        items: list[dict] = []
        for raw in stdout.decode("utf-8", "replace").splitlines():
            line = raw.strip()
            if not line or line[0] not in "[{":
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                items.append(value)
            elif isinstance(value, list):
                for candidate in value:
                    if isinstance(candidate, dict):
                        items.append(candidate)
                        break
        return items

    async def download(self, job: Job) -> Path:
        if not self.available():
            raise EngineError(
                "engine_unavailable",
                "محرّك gallery-dl غير مثبّت على الخادم. راجع دليل التشغيل.",
            )
        command = self.command() + ["-D", str(job.directory), "--no-mtime", job.url]
        job.message = "جارٍ تنزيل ألبوم الصور…"
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        job.process = process
        communication = asyncio.create_task(process.communicate())
        last_count = 0
        try:
            while not communication.done():
                await asyncio.sleep(0.4)
                files = [item for item in job.directory.rglob("*") if item.is_file()]
                if len(files) != last_count:
                    last_count = len(files)
                    size = sum(item.stat().st_size for item in files)
                    job.update(
                        progress=min(95.0, 5.0 + len(files) * 4.0),
                        downloaded=size,
                        message=f"تم تنزيل {len(files)} عنصرًا…",
                    )
                if job.cancel_requested:
                    process.terminate()
                    break
            stdout, stderr = await communication
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            job.process = None

        if job.cancel_requested:
            raise asyncio.CancelledError()
        if process.returncode != 0:
            detail = tail(stderr)
            LOGGER.info("gallery-dl failed: %s", detail)
            raise EngineError(
                "download_failed",
                "تعذّر تنزيل الألبوم. قد يكون المعرض خاصًا أو محذوفًا.",
                detail,
            )

        files = [
            item
            for item in job.directory.rglob("*")
            if item.is_file() and item.suffix.lower() != ".zip"
        ]
        if not files:
            raise EngineError("download_failed", "لم ينزّل المحرك أي صورة من هذا الرابط.")
        job.message = "جارٍ ضغط الصور في ملف ZIP…"
        archive = job.directory / (
            safe_filename(str(job.title), fallback="n3m-album")[:100] + ".zip"
        )
        count, _ = zip_directory(job.directory, archive)
        if count == 0:
            raise EngineError("download_failed", "تعذّر إنشاء أرشيف ZIP للألبوم.")
        for item in files:
            try:
                item.unlink()
            except OSError:
                pass
        job.update(
            progress=100,
            downloaded=archive.stat().st_size,
            total=archive.stat().st_size,
            message="اكتمل تجهيز الألبوم.",
        )
        return archive
