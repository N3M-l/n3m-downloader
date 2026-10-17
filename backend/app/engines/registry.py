"""Engine selection, capability status and per-request dispatch."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from ..config import Settings
from ..errors import EngineError
from ..jobs import Job
from ..platforms import PLATFORMS, detect_platform
from .direct import DirectEngine
from .ffmpeg import FFmpegEngine
from .gallerydl import GalleryDlEngine
from .ytdlp import YtDlpEngine

LOGGER = logging.getLogger("n3m.engines.registry")


class EngineSet:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ytdlp = YtDlpEngine(settings)
        self.gallerydl = GalleryDlEngine(settings)
        self.direct = DirectEngine(settings)
        self.ffmpeg = FFmpegEngine(settings)
        self._status_cache: dict | None = None
        self._status_at = 0.0
        self._lock = asyncio.Lock()

    async def status(self, *, force: bool = False) -> dict:
        async with self._lock:
            if not force and self._status_cache and time.monotonic() - self._status_at < 60:
                return self._status_cache
            ffmpeg_path = self.ffmpeg.path()
            aria_path = self.direct.aria2c()
            info = {
                "ytdlp": {
                    "available": self.ytdlp.available(),
                    "version": self.ytdlp.version(),
                    "path": self._display_path(self.ytdlp.command()),
                },
                "gallerydl": {
                    "available": self.gallerydl.available(),
                    "version": self.gallerydl.version(),
                    "path": self._display_path(self.gallerydl.command()),
                },
                "aria2c": {
                    "available": bool(aria_path),
                    "version": None,
                    "path": aria_path,
                },
                "ffmpeg": {
                    "available": bool(ffmpeg_path),
                    "version": (await self.ffmpeg.version()) if ffmpeg_path else None,
                    "path": ffmpeg_path,
                },
            }
            self._status_cache = info
            self._status_at = time.monotonic()
            return info

    @staticmethod
    def _display_path(command: list[str]) -> str | None:
        if not command:
            return None
        if command[0].lower().endswith("python.exe") and len(command) > 2:
            return f"{command[0]} -m {command[2]}"
        return command[0]

    async def inspect(self, url: str, platform_key: str | None = None) -> dict:
        platform = PLATFORMS.get(platform_key or "") or detect_platform(url)
        if platform.key == "file":
            return await self.direct.inspect(url)
        if platform.key == "pinterest":
            try:
                return await self.gallerydl.inspect(url)
            except EngineError as exc:
                LOGGER.info("gallery-dl inspect failed for pinterest: %s", exc.detail)
                return await self.ytdlp.inspect(url)
        try:
            result = await self.ytdlp.inspect(url)
        except EngineError as exc:
            if platform.key in {"instagram", "reddit"}:
                LOGGER.info("yt-dlp inspect failed, trying gallery-dl: %s", exc.detail)
                return await self.gallerydl.inspect(url)
            raise
        if platform.key == "soundcloud":
            result["kind"] = "audio"
        return result

    async def download(self, job: Job) -> Path:
        if job.mode == "images":
            return await self.gallerydl.download(job)
        if job.mode == "file":
            return await self.direct.download(job)
        return await self.ytdlp.download(job)
