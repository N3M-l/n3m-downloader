"""Asynchronous download jobs with progress, cancellation and retention."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from .config import Settings
from .errors import ApiError, EngineError
from .storage import cleanup_old_jobs, disk_status, has_quota, pick_output

LOGGER = logging.getLogger("n3m.jobs")

TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled", "expired"})
Runner = Callable[["Job"], Awaitable[Path | None]]


@dataclass
class Job:
    id: str
    url: str
    mode: str
    platform: str
    title: str
    directory: Path
    created_at: float
    status: str = "queued"
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    speed_bps: float | None = None
    eta_seconds: int | None = None
    filename: str | None = None
    output_path: Path | None = None
    error: str | None = None
    error_code: str | None = None
    message: str = "في قائمة الانتظار…"
    process: object | None = None
    cancel_requested: bool = False
    finished_at: float | None = None
    quality: str | None = None
    format_id: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def update(
        self,
        *,
        progress: float | None = None,
        downloaded: int | None = None,
        total: int | None = None,
        speed: float | None = None,
        eta: int | None = None,
        message: str | None = None,
    ) -> None:
        if progress is not None:
            self.progress = max(0.0, min(100.0, float(progress)))
        if downloaded is not None:
            self.downloaded_bytes = max(0, int(downloaded))
        if total is not None and total > 0:
            self.total_bytes = int(total)
        self.speed_bps = speed
        self.eta_seconds = eta
        if message is not None:
            self.message = message

    def snapshot(self, download_path: str | None = None) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": round(self.progress, 1),
            "speedBps": round(self.speed_bps or 0, 2),
            "etaSeconds": self.eta_seconds,
            "downloadedBytes": self.downloaded_bytes,
            "totalBytes": self.total_bytes,
            "filename": self.filename,
            "error": self.error,
            "message": self.message,
            "downloadPath": download_path if self.status == "completed" else None,
            "createdAt": int(self.created_at * 1000),
        }


class JobManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jobs: dict[str, Job] = {}
        self._tasks: set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)

    @property
    def active_count(self) -> int:
        return sum(
            1 for job in self._jobs.values() if job.status in {"queued", "running"}
        )

    @property
    def retained_count(self) -> int:
        return len(self._jobs)

    def get(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise ApiError(404, "not_found", "لم يعد هذا الطلب موجودًا. ابدأ من جديد.")
        return job

    async def create(
        self,
        *,
        url: str,
        mode: str,
        platform: str,
        title: str,
        quality: str | None,
        format_id: str | None,
        runner: Runner,
    ) -> Job:
        async with self._lock:
            active = self.active_count
            if active >= self.settings.max_queued_jobs:
                raise ApiError(
                    429,
                    "queue_full",
                    "الخادم مشغول حاليًا. انتظر قليلًا ثم أعد المحاولة.",
                )
            job_id = secrets.token_hex(8)
            directory = self.settings.jobs_dir / job_id
            directory.mkdir(parents=True, exist_ok=True)
            job = Job(
                id=job_id,
                url=url,
                mode=mode,
                platform=platform,
                title=title,
                directory=directory,
                created_at=time.time(),
                quality=quality,
                format_id=format_id,
            )
            self._jobs[job_id] = job
        task = asyncio.create_task(self._run(job, runner), name=f"job-{job_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(self, job: Job, runner: Runner) -> None:
        try:
            async with self._semaphore:
                if job.cancel_requested:
                    raise asyncio.CancelledError()
                job.status = "running"
                job.message = "جارٍ تجهيز التحميل…"
                status = disk_status(self.settings.work_dir, self.settings.min_free_gb)
                if not status["ok"]:
                    raise ApiError(
                        503,
                        "quota_exceeded",
                        "مساحة الخادم ممتلئة تقريبًا. جرّب لاحقًا.",
                    )
                output = await asyncio.wait_for(
                    runner(job), timeout=self.settings.job_timeout_seconds
                )
                if job.cancel_requested:
                    raise asyncio.CancelledError()
                if output is None or not output.exists():
                    output = pick_output(job.directory)
                if output is None or not output.is_file() or output.stat().st_size <= 0:
                    raise ApiError(
                        502,
                        "download_failed",
                        "لم يكتمل إنشاء الملف. حاول مرة أخرى.",
                    )
                job.output_path = output
                job.filename = output.name
                job.total_bytes = job.total_bytes or output.stat().st_size
                job.downloaded_bytes = output.stat().st_size
                job.progress = 100.0
                job.speed_bps = None
                job.eta_seconds = 0
                job.status = "completed"
                job.message = "اكتمل التحميل — جارٍ الحفظ."
        except asyncio.CancelledError:
            job.status = "cancelled"
            job.message = "تم إلغاء التحميل."
        except asyncio.TimeoutError:
            job.status = "failed"
            job.error_code = "timeout"
            job.error = "استغرق التحميل وقتًا أطول من المسموح. جرّب رابطًا أصغر."
            job.message = job.error
        except ApiError as exc:
            job.status = "failed"
            job.error_code = exc.code
            job.error = exc.message
            job.message = exc.message
        except EngineError as exc:
            job.status = "failed"
            job.error_code = exc.code
            job.error = exc.message
            job.message = exc.message
            if exc.detail:
                LOGGER.info("engine detail for %s: %s", job.id, exc.detail[-800:])
        except Exception:
            LOGGER.exception("unexpected job failure %s", job.id)
            job.status = "failed"
            job.error_code = "download_failed"
            job.error = "حدث خطأ غير متوقع أثناء التحميل. حاول مرة أخرى."
            job.message = job.error
        finally:
            job.finished_at = time.time()
            job.process = None
            job.speed_bps = None
            job.eta_seconds = None

    async def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.terminal:
            return job
        job.cancel_requested = True
        job.message = "جارٍ الإلغاء…"
        process = job.process
        if process is not None:
            try:
                process.terminate()  # type: ignore[attr-defined]
            except (ProcessLookupError, OSError):
                pass
        return job

    def cleanup(self) -> dict[str, int]:
        result = cleanup_old_jobs(self.settings.jobs_dir, self.settings.job_retention_minutes)
        cutoff = time.time() - self.settings.job_retention_minutes * 60
        stale = [
            job_id
            for job_id, job in self._jobs.items()
            if job.finished_at is not None and job.finished_at < cutoff
        ]
        for job_id in stale:
            self._jobs.pop(job_id, None)
        result["removedJobs"] = result.get("removedJobs", 0)
        return result

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()


def quota_precheck(settings: Settings, incoming_bytes: int = 0) -> None:
    if not has_quota(settings.work_dir, settings.min_free_gb, incoming_bytes):
        raise ApiError(
            503,
            "quota_exceeded",
            "لا توجد مساحة كافية على الخادم لبدء هذا التحميل.",
        )
