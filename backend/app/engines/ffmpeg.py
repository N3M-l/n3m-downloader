"""FFmpeg capability probe (merging and audio extraction are delegated to yt-dlp)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from ..config import Settings
from .base import run_process

LOGGER = logging.getLogger("n3m.ffmpeg")


class FFmpegEngine:
    key = "ffmpeg"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def path(self) -> str | None:
        configured = self.settings.ffmpeg_path
        if configured and (Path(configured).is_file() or shutil.which(configured)):
            return configured
        return shutil.which("ffmpeg")

    def available(self) -> bool:
        return self.path() is not None

    async def version(self) -> str | None:
        executable = self.path()
        if not executable:
            return None
        try:
            code, stdout, stderr = await run_process([executable, "-version"], timeout=5)
        except Exception:  # pragma: no cover - defensive
            return None
        if code != 0:
            return None
        line = (stdout or stderr).decode("utf-8", "replace").splitlines()
        return line[0].strip() if line else None
