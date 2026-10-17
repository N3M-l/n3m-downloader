"""FastAPI application for the N3M Downloader engine.

Security model:
- browser callers must present a trusted Origin (n3m.fun by default);
- the admin surface additionally requires a Bearer admin token;
- direct file delivery uses a short-lived signed ticket, not an Origin.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import mimetypes
import platform as platform_module
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Literal

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings, trusted_origins_from_env
from .engines.registry import EngineSet
from .errors import ApiError, EngineError
from .jobs import JobManager, quota_precheck
from .platforms import detect_platform, suggested_mode
from .rate_limit import SlidingWindowLimiter, client_ip
from .ssrf import validate_public_url
from .storage import cleanup_tmp, disk_status
from .tickets import TicketError, sign_ticket, verify_ticket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("n3m.api")

SETUP_HINT = (
    "تأكد من تثبيت yt-dlp وgallery-dl (عبر requirements.txt) وFFmpeg وaria2c على الخادم."
)


class InspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=4, max_length=2048)


class DownloadRequest(InspectRequest):
    mode: Literal["video", "audio", "images", "file"] = "video"
    quality: str | None = Field(default=None, max_length=16)
    format_id: str | None = Field(default=None, max_length=32, alias="formatId")


class SecurityMiddleware(BaseHTTPMiddleware):
    """Origin gate for browser calls plus baseline response headers."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        method = request.method
        settings: Settings = request.app.state.settings

        if (
            method != "OPTIONS"
            and path.startswith("/api/")
            and not path.startswith("/api/download/")
            and not path.startswith("/api/admin/")
        ):
            origin = request.headers.get("origin")
            if not settings.origin_allowed(origin):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "unauthorized",
                            "message": "هذا الطلب غير مصرّح به. افتح الأداة من الموقع الرسمي.",
                        }
                    },
                )

        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response


def _json_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = settings or Settings.from_env()
        resolved.prepare_dirs()
        app.state.settings = resolved
        app.state.started_at = time.time()
        app.state.jobs = JobManager(resolved)
        app.state.engines = EngineSet(resolved)
        app.state.inspect_limiter = SlidingWindowLimiter(resolved.inspect_rate_per_min)
        app.state.download_limiter = SlidingWindowLimiter(resolved.download_rate_per_min)
        app.state.admin_limiter = SlidingWindowLimiter(resolved.admin_rate_per_min)

        cleanup_task = asyncio.create_task(_cleanup_loop(app))
        try:
            yield
        finally:
            cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup_task
            await app.state.jobs.shutdown()

    app = FastAPI(
        title="N3M Downloader Engine",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.trusted_origins if settings else trusted_origins_from_env()),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        expose_headers=["Content-Disposition", "Retry-After"],
        max_age=600,
    )

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        headers = {}
        retry = exc.details.get("retryAfter")
        if isinstance(retry, int):
            headers["Retry-After"] = str(retry)
        return JSONResponse(status_code=exc.status_code, content=exc.payload(), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        LOGGER.info("validation error: %s", exc.errors()[:2])
        return _json_error(400, "invalid_request", "البيانات المرسلة غير صالحة. تحقّق من الرابط.")

    @app.exception_handler(EngineError)
    async def handle_engine(_: Request, exc: EngineError) -> JSONResponse:
        return _json_error(502, exc.code, exc.message)

    @app.get("/")
    async def root() -> dict:
        return {"name": "N3M Downloader Engine", "version": "1.0.0"}

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/health")
    async def api_health(request: Request) -> dict:
        settings: Settings = request.app.state.settings
        return {
            "status": "ok",
            "version": settings.version,
            "uptimeSeconds": int(time.time() - request.app.state.started_at),
        }

    async def _limit(request: Request, bucket: str) -> None:
        settings: Settings = request.app.state.settings
        limiter: SlidingWindowLimiter = getattr(request.app.state, f"{bucket}_limiter")
        address = client_ip(request, trust_proxy=settings.trust_proxy)
        allowed, retry = await limiter.check(f"{bucket}:{address}")
        if not allowed:
            raise ApiError(
                429,
                "rate_limited",
                f"محاولات كثيرة في وقت قصير. انتظر {retry} ثانية ثم أعد المحاولة.",
                {"retryAfter": retry},
            )

    async def inspect_limit(request: Request) -> None:
        await _limit(request, "inspect")

    async def download_limit(request: Request) -> None:
        await _limit(request, "download")

    async def admin_limit(request: Request) -> None:
        await _limit(request, "admin")

    async def require_admin(request: Request) -> None:
        settings: Settings = request.app.state.settings
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise ApiError(401, "unauthorized", "مطلوب رمز إدارة للوصول إلى هذه اللوحة.")
        token = auth[7:].strip()
        if not hmac.compare_digest(token, settings.admin_token):
            raise ApiError(403, "forbidden", "رمز الإدارة غير صحيح.")

    @app.post("/api/inspect", dependencies=[Depends(inspect_limit)])
    async def inspect(payload: InspectRequest, request: Request) -> dict:
        settings: Settings = request.app.state.settings
        url = payload.url.strip()
        validated = await asyncio.to_thread(validate_public_url, url)
        platform = detect_platform(validated.url)
        try:
            result = await request.app.state.engines.inspect(validated.url, platform.key)
        except EngineError as exc:
            raise ApiError(
                502,
                exc.code,
                exc.message,
                {"hint": SETUP_HINT} if exc.code == "engine_unavailable" else None,
            ) from exc

        kind = result.get("kind") or platform.kind
        mode = suggested_mode(platform)
        if kind == "images":
            mode = "images"
        elif kind == "file":
            mode = "file"
        return {
            "url": validated.url,
            "platform": platform.key,
            "platformLabel": platform.label,
            "platformEmoji": platform.emoji,
            "kind": kind,
            "title": result.get("title") or "وسائط N3M",
            "uploader": result.get("uploader"),
            "durationSeconds": result.get("durationSeconds"),
            "thumbnail": result.get("thumbnail"),
            "filesizeBytes": result.get("filesizeBytes"),
            "formats": result.get("formats") or [],
            "suggestedMode": mode,
            "expiresAt": int((time.time() + settings.ticket_ttl_seconds) * 1000),
        }

    @app.post("/api/download", status_code=202, dependencies=[Depends(download_limit)])
    async def download(payload: DownloadRequest, request: Request) -> JSONResponse:
        settings: Settings = request.app.state.settings
        url = payload.url.strip()
        validated = await asyncio.to_thread(validate_public_url, url)
        platform = detect_platform(validated.url)
        quota_precheck(settings)

        title = platform.label
        if platform.key == "file":
            from urllib.parse import unquote, urlsplit

            title = unquote(urlsplit(validated.url).path.rsplit("/", 1)[-1]) or "ملف N3M"
        job = await request.app.state.jobs.create(
            url=validated.url,
            mode=payload.mode,
            platform=platform.key,
            title=title,
            quality=payload.quality,
            format_id=payload.format_id,
            runner=request.app.state.engines.download,
        )
        return JSONResponse(
            status_code=202,
            content={
                "jobId": job.id,
                "status": job.status,
                "pollUrl": f"/api/jobs/{job.id}",
                "eventsUrl": f"/api/jobs/{job.id}/events",
                "cancelUrl": f"/api/jobs/{job.id}/cancel",
            },
        )

    def snapshot(request: Request, job_id: str) -> dict:
        settings: Settings = request.app.state.settings
        job = request.app.state.jobs.get(job_id)
        download_path = None
        if job.status == "completed" and job.output_path and job.output_path.is_file():
            token = sign_ticket(
                settings.ticket_secret,
                job.id,
                ttl_seconds=settings.ticket_ttl_seconds,
            )
            download_path = f"/api/download/{token}"
        return job.snapshot(download_path)

    @app.get("/api/jobs/{job_id}")
    async def job_status(job_id: str, request: Request) -> dict:
        return snapshot(request, job_id)

    @app.post("/api/jobs/{job_id}/cancel", dependencies=[Depends(download_limit)])
    async def cancel_job(job_id: str, request: Request) -> dict:
        job = await request.app.state.jobs.cancel(job_id)
        return job.snapshot()

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str, request: Request) -> StreamingResponse:
        request.app.state.jobs.get(job_id)

        async def stream() -> AsyncIterator[str]:
            last_emit = 0.0
            while True:
                if await request.is_disconnected():
                    break
                body = snapshot(request, job_id)
                yield f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
                if body["status"] in {"completed", "failed", "cancelled"}:
                    break
                last_emit = time.monotonic()
                await asyncio.sleep(0.6)
                if time.monotonic() - last_emit > 15:
                    yield ": ping\n\n"
            yield "event: end\ndata: {}\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/download/{token}")
    async def download_file(token: str, request: Request) -> FileResponse:
        settings: Settings = request.app.state.settings
        try:
            payload = verify_ticket(settings.ticket_secret, token)
        except TicketError as exc:
            status = 410 if exc.reason == "expired" else 401
            raise ApiError(status, exc.reason, exc.message) from exc
        job = request.app.state.jobs.get(str(payload["j"]))
        if job.status != "completed" or job.output_path is None:
            raise ApiError(409, "not_ready", "الملف غير جاهز بعد. انتظر اكتمال التحميل.")
        path = job.output_path.resolve()
        if not path.is_file() or not path.is_relative_to(settings.jobs_dir.resolve()):
            raise ApiError(410, "expired", "انتهت صلاحية الملف. أعد التحميل من جديد.")
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(
            path,
            media_type=media_type,
            filename=job.filename or path.name,
            headers={"Cache-Control": "private, no-store"},
        )

    @app.get("/api/admin/status", dependencies=[Depends(require_admin), Depends(admin_limit)])
    async def admin_status(request: Request) -> dict:
        settings: Settings = request.app.state.settings
        engines = await request.app.state.engines.status(force=True)
        return {
            "status": "online",
            "version": settings.version,
            "arch": platform_module.machine(),
            "system": f"{platform_module.system()} {platform_module.release()}",
            "hostname": platform_module.node(),
            "uptimeSeconds": int(time.time() - request.app.state.started_at),
            "engines": engines,
            "disk": disk_status(settings.work_dir, settings.min_free_gb),
            "jobs": {
                "active": request.app.state.jobs.active_count,
                "retained": request.app.state.jobs.retained_count,
                "maxConcurrent": settings.max_concurrent_jobs,
            },
            "limits": {
                "inspectPerMinute": settings.inspect_rate_per_min,
                "downloadsPerMinute": settings.download_rate_per_min,
                "maxFilesizeMb": settings.max_filesize_mb,
                "ticketTtlSeconds": settings.ticket_ttl_seconds,
                "retentionMinutes": settings.job_retention_minutes,
            },
            "workDir": str(settings.work_dir),
        }

    @app.post(
        "/api/admin/cleanup",
        dependencies=[Depends(require_admin), Depends(admin_limit)],
    )
    async def admin_cleanup(request: Request) -> dict:
        settings: Settings = request.app.state.settings
        result = request.app.state.jobs.cleanup()
        tmp = cleanup_tmp(settings.tmp_dir)
        return {
            "freedBytes": result.get("freedBytes", 0) + tmp["freedBytes"],
            "removedJobs": result.get("removedJobs", 0),
            "disk": disk_status(settings.work_dir, settings.min_free_gb),
        }

    return app


async def _cleanup_loop(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    while True:
        await asyncio.sleep(1800)
        try:
            result = app.state.jobs.cleanup()
            if result.get("removedJobs"):
                LOGGER.info("cleanup removed %s jobs", result["removedJobs"])
        except Exception:  # pragma: no cover - maintenance must not crash the app
            LOGGER.exception("cleanup loop failed")


app = create_app()
