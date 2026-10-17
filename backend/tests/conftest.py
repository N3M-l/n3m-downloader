from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("PYTHONUTF8", "1")

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

# A harness-provisioned parent keeps runtime test directories readable on Windows.
TEST_ROOT = BACKEND / "tmpbase"


def new_directory(label: str) -> Path:
    path = TEST_ROOT / f"{label}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path



class StubEngines:
    """Deterministic replacement for the real media engines."""

    def __init__(self, *, content: bytes = b"0123456789", delay: float = 0.0) -> None:
        self.content = content
        self.delay = delay
        self.inspected: list[str] = []

    async def inspect(self, url: str, platform_key: str | None = None) -> dict:
        self.inspected.append(url)
        return {
            "title": "Demo video",
            "uploader": "tester",
            "durationSeconds": 12.5,
            "thumbnail": None,
            "filesizeBytes": len(self.content),
            "formats": [
                {
                    "id": "best",
                    "label": "best",
                    "ext": "mp4",
                    "height": 720,
                    "audioBitrate": None,
                    "sizeBytes": len(self.content),
                }
            ],
            "kind": "video",
        }

    async def status(self, *, force: bool = False) -> dict:
        return {
            "ytdlp": {"available": True, "version": "test", "path": "yt-dlp"},
            "gallerydl": {"available": True, "version": "test", "path": "gallery-dl"},
            "aria2c": {"available": False, "version": None, "path": None},
            "ffmpeg": {"available": False, "version": None, "path": None},
        }

    async def download(self, job) -> Path:
        if self.delay:
            import asyncio

            await asyncio.sleep(self.delay)
        target = job.directory / "demo.mp4"
        target.write_bytes(self.content)
        job.update(progress=100, downloaded=len(self.content), total=len(self.content))
        return target


@pytest.fixture()
def workdir() -> Path:
    return new_directory("work")


@pytest.fixture()
def settings(workdir, monkeypatch) -> Settings:
    monkeypatch.setenv("N3M_ENV", "test")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("TICKET_SECRET", "test-ticket-secret")
    monkeypatch.setenv("N3M_WORK_DIR", str(workdir / "engine"))
    monkeypatch.setenv("TRUSTED_ORIGINS", "https://n3m.fun,http://localhost:3000")
    monkeypatch.setenv("INSPECT_RATE_PER_MIN", "30")
    monkeypatch.setenv("DOWNLOAD_RATE_PER_MIN", "6")
    return Settings.from_env()


@pytest.fixture()
def app(settings):
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def trusted_headers() -> dict[str, str]:
    return {"Origin": "https://n3m.fun"}


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-admin-token"}
