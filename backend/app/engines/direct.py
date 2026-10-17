"""Direct-file engine: aria2c acceleration with a streamed httpx fallback."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from ..config import REDIRECT_STATUSES, USER_AGENT, Settings
from ..errors import ApiError, EngineError
from ..jobs import Job
from ..ssrf import safe_head, validate_public_url
from ..storage import ensure_extension, has_quota, safe_filename
from .progress import parse_eta, parse_speed

LOGGER = logging.getLogger("n3m.direct")

ARIA2_PERCENT = re.compile(r"\((\d{1,3})%\)")
ARIA2_SPEED = re.compile(r"\bDL:([\d.]+[KMG]?i?B)", re.IGNORECASE)
ARIA2_ETA = re.compile(r"\bETA:([\d]+[smh]?)", re.IGNORECASE)

CONTENT_TYPE_EXTENSIONS = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/x-matroska": "mkv",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/wav": "wav",
    "audio/flac": "flac",
    "application/zip": "zip",
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


class DirectEngine:
    key = "direct"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def aria2c(self) -> str | None:
        configured = self.settings.aria2c_path
        if configured and (Path(configured).is_file() or shutil.which(configured)):
            return configured
        return shutil.which("aria2c")

    async def inspect(self, url: str) -> dict:
        head = await safe_head(url, timeout=self.settings.request_timeout_seconds)
        if head.content_length and head.content_length > self.settings.max_filesize_mb * 1024**2:
            raise ApiError(
                413,
                "too_large",
                f"حجم الملف يتجاوز الحد المسموح ({self.settings.max_filesize_mb} ميجابايت).",
            )
        filename = safe_filename(head.filename or self._name_from_url(url), fallback="n3m-file")
        extension = Path(filename).suffix.lstrip(".")
        if not extension:
            extension = CONTENT_TYPE_EXTENSIONS.get(head.content_type.split(";")[0].strip(), "")
            filename = ensure_extension(filename, extension) if extension else filename
        return {
            "title": filename,
            "uploader": None,
            "durationSeconds": None,
            "thumbnail": None,
            "filesizeBytes": head.content_length,
            "formats": [
                {
                    "id": "original",
                    "label": "الملف الأصلي",
                    "ext": extension or "bin",
                    "height": None,
                    "audioBitrate": None,
                    "sizeBytes": head.content_length,
                }
            ],
            "kind": "file",
        }

    def _name_from_url(self, url: str) -> str:
        path = unquote(urlsplit(url).path)
        return path.rsplit("/", 1)[-1] or "n3m-file"

    async def download(self, job: Job) -> Path:
        filename = safe_filename(job.title, fallback="n3m-file")
        destination = job.directory / filename
        aria = self.aria2c()
        if aria:
            try:
                return await self._download_with_aria2c(job, aria, destination)
            except FileNotFoundError:
                LOGGER.info("aria2c disappeared; falling back to stream")
            except EngineError as exc:
                if "غير مثبّت" in exc.message:
                    LOGGER.info("aria2c unavailable: %s", exc)
                else:
                    raise
        return await self._download_with_stream(job, destination)

    async def _download_with_aria2c(self, job: Job, aria: str, destination: Path) -> Path:
        command = [
            aria,
            "--dir",
            str(job.directory),
            "--out",
            destination.name,
            "--max-connection-per-server=8",
            "--split=8",
            "--min-split-size=1M",
            "--file-allocation=none",
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
            "--summary-interval=1",
            "--console-log-level=warn",
            "--download-result=hide",
            job.url,
        ]
        job.message = "جارٍ تنزيل الملف بسرعة…"
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        job.process = process
        stderr_chunks: list[bytes] = []

        async def collect_stderr() -> None:
            assert process.stderr is not None
            while True:
                chunk = await process.stderr.read(2048)
                if not chunk:
                    break
                stderr_chunks.append(chunk)
                if len(stderr_chunks) > 40:
                    stderr_chunks.pop(0)

        stderr_task = asyncio.create_task(collect_stderr())
        try:
            assert process.stdout is not None
            while True:
                raw = await process.stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", "replace")
                percent = ARIA2_PERCENT.search(line)
                speed_match = ARIA2_SPEED.search(line)
                eta_match = ARIA2_ETA.search(line)
                if percent:
                    pct = float(percent.group(1))
                    job.update(
                        progress=min(99.0, pct),
                        speed=parse_speed(speed_match.group(1)) if speed_match else None,
                        eta=parse_eta(eta_match.group(1)) if eta_match else None,
                        message=f"جارٍ التنزيل… {pct:.0f}%",
                    )
            code = await process.wait()
            await stderr_task
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            job.process = None
        if job.cancel_requested:
            raise asyncio.CancelledError()
        if code != 0:
            detail = b"".join(stderr_chunks).decode("utf-8", "replace")[-600:]
            LOGGER.info("aria2c failed (%s): %s", code, detail)
            raise EngineError(
                "download_failed",
                "تعذّر إكمال تنزيل الملف. قد يكون الرابط محذوفًا أو محميًا.",
                detail,
            )
        if not destination.is_file() or destination.stat().st_size == 0:
            raise EngineError("download_failed", "لم ينتج المحرك ملفًا قابلًا للحفظ.")
        job.update(
            progress=100,
            downloaded=destination.stat().st_size,
            total=destination.stat().st_size,
            message="اكتمل التحميل.",
        )
        return destination

    async def _download_with_stream(self, job: Job, destination: Path) -> Path:
        current = job.url
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        max_bytes = self.settings.max_filesize_mb * 1024**2
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(self.settings.request_timeout_seconds),
        ) as client:
            for _ in range(6):
                validated = await asyncio.to_thread(validate_public_url, current)
                async with client.stream("GET", validated.url, headers=headers) as response:
                    if response.status_code in REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise EngineError("download_failed", "أعاد الخادم تحويلًا غير مكتمل.")
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 400:
                        raise EngineError(
                            "download_failed",
                            "تعذّر الوصول إلى الملف. قد يكون محذوفًا أو محميًا.",
                            f"HTTP {response.status_code}",
                        )
                    disposition = response.headers.get("content-disposition") or ""
                    filename = destination.name
                    if "filename" in disposition.lower():
                        from ..ssrf import _filename_from_disposition

                        suggested = _filename_from_disposition(disposition)
                        if suggested:
                            filename = safe_filename(suggested, fallback=destination.name)
                    target = job.directory / filename
                    if target.suffix == "" and destination.suffix:
                        target = ensure_extension(target, destination.suffix.lstrip("."))
                    total_header = response.headers.get("content-length")
                    total = int(total_header) if total_header and total_header.isdigit() else None
                    if total and total > max_bytes:
                        raise EngineError(
                            "too_large",
                            f"حجم الملف يتجاوز الحد المسموح ({self.settings.max_filesize_mb} ميجابايت).",
                        )
                    part = target.with_suffix(target.suffix + ".part")
                    downloaded = 0
                    job.update(message="جارٍ تنزيل الملف…", total=total)
                    with part.open("wb") as handle:
                        async for chunk in response.aiter_bytes(65536):
                            if job.cancel_requested:
                                raise asyncio.CancelledError()
                            handle.write(chunk)
                            downloaded += len(chunk)
                            if downloaded > max_bytes:
                                handle.close()
                                part.unlink(missing_ok=True)
                                raise EngineError(
                                    "too_large",
                                    f"حجم الملف يتجاوز الحد المسموح ({self.settings.max_filesize_mb} ميجابايت).",
                                )
                            if downloaded % (4 * 1024 * 1024) < 65536 and not has_quota(
                                self.settings.work_dir, self.settings.min_free_gb
                            ):
                                handle.close()
                                part.unlink(missing_ok=True)
                                raise ApiError(
                                    503,
                                    "quota_exceeded",
                                    "نفدت مساحة الخادم أثناء التحميل.",
                                )
                            percent = (downloaded / total * 100) if total else None
                            job.update(
                                progress=percent if percent is not None else min(95.0, job.progress + 0.2),
                                downloaded=downloaded,
                                total=total,
                            )
                    if target.exists():
                        target.unlink()
                    part.replace(target)
                    job.update(
                        progress=100,
                        downloaded=downloaded,
                        total=total or downloaded,
                        message="اكتمل التحميل.",
                    )
                    return target
        raise EngineError("download_failed", "الرابط يعيد التوجيه مرات كثيرة جدًا.")
