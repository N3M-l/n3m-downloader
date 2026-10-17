"""yt-dlp engine: metadata inspection and video/audio downloads."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import sys
from pathlib import Path

from ..config import Settings
from ..errors import EngineError
from ..jobs import Job
from ..storage import ensure_extension, pick_output, safe_filename
from .base import module_available, package_version, run_process, tail
from .progress import parse_bytes, parse_eta, parse_percent, parse_speed

LOGGER = logging.getLogger("n3m.ytdlp")

PROGRESS_PREFIX = "N3MPROG"
PROGRESS_TEMPLATE = (
    "download:N3MPROG|%(progress._percent_str)s|%(progress.speed)s|"
    "%(progress.eta)s|%(progress.downloaded_bytes)s|%(progress.total_bytes)s"
)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class YtDlpEngine:
    key = "ytdlp"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ------------------------------------------------------------------ paths
    def command(self) -> list[str]:
        configured = self.settings.ytdlp_path
        if configured:
            return [configured]
        executable = shutil.which("yt-dlp")
        if executable:
            return [executable]
        return [sys.executable, "-m", "yt_dlp"]

    def available(self) -> bool:
        if self.settings.ytdlp_path:
            return Path(self.settings.ytdlp_path).exists() or bool(
                shutil.which(self.settings.ytdlp_path)
            )
        return bool(shutil.which("yt-dlp")) or module_available("yt_dlp")

    def version(self) -> str | None:
        return package_version("yt-dlp")

    def ffmpeg(self) -> str | None:
        configured = self.settings.ffmpeg_path
        if configured and (Path(configured).is_file() or shutil.which(configured)):
            return configured
        return shutil.which("ffmpeg")

    # ----------------------------------------------------------------- inspect
    async def inspect(self, url: str) -> dict:
        if not self.available():
            raise EngineError(
                "engine_unavailable",
                "محرّك yt-dlp غير مثبّت على الخادم. راجع دليل التشغيل.",
            )
        command = self.command() + [
            "--dump-single-json",
            "--no-playlist",
            "--no-warnings",
            "--socket-timeout",
            "15",
            url,
        ]
        code, stdout, stderr = await run_process(command, timeout=75)
        if code != 0:
            detail = tail(stderr)
            LOGGER.info("yt-dlp inspect failed: %s", detail)
            raise EngineError(
                "inspect_failed",
                "تعذّر تحليل هذا الرابط. تأكد أن المحتوى عام وليس خاصًا أو محميًا.",
                detail,
            )
        try:
            data = json.loads(stdout.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            raise EngineError(
                "inspect_failed",
                "أعاد المحرك بيانات غير مفهومة لهذا الرابط.",
                tail(stdout),
            ) from exc

        if not isinstance(data, dict):
            raise EngineError("inspect_failed", "هذا الرابط لا يشير إلى عنصر واحد قابل للتحميل.")
        if data.get("_type") == "playlist":
            entries = [item for item in data.get("entries") or [] if isinstance(item, dict)]
            if not entries:
                raise EngineError("inspect_failed", "قائمة التشغيل فارغة أو غير متاحة.")
            data = entries[0]
        if data.get("is_live"):
            raise EngineError(
                "live_unsupported",
                "البث المباشر غير مدعوم. انتظر انتهاء البث ثم أعد المحاولة.",
            )

        title = str(data.get("title") or data.get("fulltitle") or "وسائط N3M")
        duration = data.get("duration")
        thumbnail = data.get("thumbnail")
        if not isinstance(thumbnail, str) or not thumbnail.startswith(("http://", "https://")):
            thumbnail = None

        formats = self._format_options(data)
        best = next((item for item in formats if item["id"] == "best"), None)
        return {
            "title": title[:300],
            "uploader": str(data.get("uploader") or data.get("channel") or "") or None,
            "durationSeconds": float(duration) if isinstance(duration, (int, float)) else None,
            "thumbnail": thumbnail,
            "filesizeBytes": best.get("sizeBytes") if best else None,
            "formats": formats,
            "kind": "audio" if data.get("vcodec") == "none" else "video",
        }

    def _format_options(self, data: dict) -> list[dict]:
        formats = data.get("formats") or []
        by_height: dict[int, dict] = {}
        audio_size: int | None = None
        for item in formats:
            if not isinstance(item, dict):
                continue
            vcodec = item.get("vcodec")
            acodec = item.get("acodec")
            ext = str(item.get("ext") or "").lower()
            size = item.get("filesize") or item.get("filesize_approx")
            if vcodec and vcodec != "none" and ext in {"mp4", "webm"}:
                height = item.get("height")
                if not isinstance(height, int) or height <= 0:
                    continue
                tbr = float(item.get("tbr") or 0)
                current = by_height.get(height)
                if current is None or tbr > float(current.get("tbr") or 0):
                    by_height[height] = {
                        "height": height,
                        "ext": ext,
                        "size": int(size) if isinstance(size, (int, float)) else None,
                        "tbr": tbr,
                    }
            if acodec and acodec != "none" and (not vcodec or vcodec == "none"):
                if isinstance(size, (int, float)) and (audio_size is None or size > audio_size):
                    audio_size = int(size)

        options: list[dict] = []
        best_height = max(by_height, default=0)
        best_size = by_height.get(best_height, {}).get("size") if best_height else None
        options.append(
            {
                "id": "best",
                "label": "أفضل جودة متاحة",
                "ext": "mp4",
                "height": best_height or None,
                "audioBitrate": None,
                "sizeBytes": best_size,
            }
        )
        for height in sorted(by_height, reverse=True):
            if height == best_height or len(options) >= 6:
                continue
            entry = by_height[height]
            options.append(
                {
                    "id": str(height),
                    "label": f"{height}p",
                    "ext": entry["ext"],
                    "height": height,
                    "audioBitrate": None,
                    "sizeBytes": entry["size"],
                }
            )
        options.append(
            {
                "id": "audio",
                "label": "صوت MP3",
                "ext": "mp3",
                "height": None,
                "audioBitrate": 192,
                "sizeBytes": audio_size,
            }
        )
        return options

    # ---------------------------------------------------------------- download
    async def download(self, job: Job) -> Path:
        if not self.available():
            raise EngineError(
                "engine_unavailable",
                "محرّك yt-dlp غير مثبّت على الخادم. راجع دليل التشغيل.",
            )
        ffmpeg = self.ffmpeg()
        audio = job.mode == "audio"
        quality = (job.quality or "").strip()
        if audio:
            selector = "bestaudio[ext=m4a]/bestaudio/best"
        elif quality.isdigit():
            height = int(quality)
            selector = (
                f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"best[height<={height}][ext=mp4]/best[height<={height}]"
            )
        elif ffmpeg:
            selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:
            selector = "best[ext=mp4]/best"

        template = str(job.directory / "%(title).100B [%(id)s].%(ext)s")
        command = self.command() + [
            "--no-playlist",
            "--newline",
            "--no-warnings",
            "--no-color",
            "--socket-timeout",
            "20",
            "--retries",
            "3",
            "--fragment-retries",
            "3",
            "--max-filesize",
            f"{self.settings.max_filesize_mb}M",
            "--progress-template",
            PROGRESS_TEMPLATE,
            "-f",
            selector,
            "-o",
            template,
        ]
        if audio and ffmpeg:
            command += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        elif not audio and ffmpeg:
            command += ["--merge-output-format", "mp4"]
        if ffmpeg and self.settings.ffmpeg_path:
            command += ["--ffmpeg-location", self.settings.ffmpeg_path]
        command.append(job.url)

        job.message = "جارٍ تنزيل الصوت…" if audio else "جارٍ تنزيل الفيديو…"
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
                chunk = await process.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks.append(chunk)
                if sum(len(part) for part in stderr_chunks) > 64 * 1024:
                    stderr_chunks.pop(0)

        stderr_task = asyncio.create_task(collect_stderr())
        try:
            assert process.stdout is not None
            while True:
                raw = await process.stdout.readline()
                if not raw:
                    break
                line = ANSI_RE.sub("", raw.decode("utf-8", "replace")).strip()
                if PROGRESS_PREFIX in line:
                    self._apply_progress(job, line.split(PROGRESS_PREFIX, 1)[-1].lstrip("|"))
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
            detail = tail(b"".join(stderr_chunks))
            LOGGER.info("yt-dlp download failed (%s): %s", code, detail)
            raise EngineError(
                "download_failed",
                "تعذّر إكمال التحميل. قد يكون الرابط محميًا أو غير متاح مؤقتًا.",
                detail,
            )

        output = pick_output(job.directory)
        if output is None:
            raise EngineError("download_failed", "لم ينتج المحرك أي ملف قابل للحفظ.")
        extension = output.suffix.lstrip(".") or ("mp3" if audio else "mp4")
        target = job.directory / ensure_extension(safe_filename(job.title), extension)
        if target.exists():
            target = job.directory / f"{target.stem}-{job.id[:6]}.{extension}"
        try:
            output.replace(target)
        except OSError:
            target = output
        job.update(progress=100, downloaded=target.stat().st_size, message="اكتمل التحميل.")
        return target

    def _apply_progress(self, job: Job, payload: str) -> None:
        parts = payload.split("|")
        if len(parts) < 5:
            return
        percent = parse_percent(parts[0])
        speed = parse_speed(parts[1])
        eta = parse_eta(parts[2])
        downloaded = parse_bytes(parts[3])
        total = parse_bytes(parts[4])
        job.update(
            progress=percent,
            speed=speed,
            eta=eta,
            downloaded=int(downloaded) if downloaded is not None else None,
            total=int(total) if total is not None else None,
            message=f"جارٍ التنزيل… {percent:.0f}%" if percent is not None else "جارٍ التنزيل…",
        )
