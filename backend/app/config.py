"""Runtime configuration for the N3M Downloader engine.

All values come from the process environment (optionally seeded by backend/.env).
Secrets are generated in development when absent; production refuses to start
without them.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

LOGGER = logging.getLogger("n3m.config")

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_WORK_DIR = BACKEND_ROOT / ".work"

# Local development origins; production adds https://n3m.fun explicitly.
DEFAULT_TRUSTED_ORIGINS = (
    "https://n3m.fun,https://www.n3m.fun,"
    "http://localhost:3000,http://127.0.0.1:3000"
)

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
USER_AGENT = "N3M-Downloader/1.0 (+https://n3m.fun/downloader/)"


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE pairs without overriding the real environment."""
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value[:1] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        LOGGER.warning("ignoring non-integer %s=%r", name, raw)
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        LOGGER.warning("ignoring non-numeric %s=%r", name, raw)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_origins(name: str, default: str) -> tuple[str, ...]:
    raw = _env(name) or default
    seen: list[str] = []
    for item in raw.split(","):
        origin = item.strip().rstrip("/").lower()
        if origin and origin not in seen:
            seen.append(origin)
    return tuple(seen)


@dataclass(frozen=True, slots=True)
class Settings:
    env: str
    version: str
    admin_token: str
    ticket_secret: str
    ticket_ttl_seconds: int
    trusted_origins: tuple[str, ...]
    inspect_rate_per_min: int
    download_rate_per_min: int
    admin_rate_per_min: int
    max_concurrent_jobs: int
    max_queued_jobs: int
    job_timeout_seconds: int
    job_retention_minutes: int
    min_free_gb: float
    max_filesize_mb: int
    max_url_length: int
    request_timeout_seconds: int
    trust_proxy: bool
    work_dir: Path
    ytdlp_path: str
    gallerydl_path: str
    aria2c_path: str
    ffmpeg_path: str
    ytdlp_player_client: str

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def jobs_dir(self) -> Path:
        return self.work_dir / "jobs"

    @property
    def tmp_dir(self) -> Path:
        return self.work_dir / "tmp"

    def origin_allowed(self, origin: str | None) -> bool:
        if not origin:
            return False
        return origin.strip().rstrip("/").lower() in self.trusted_origins

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(BACKEND_ROOT / ".env")
        env = _env("N3M_ENV", "development").lower()
        production = env == "production"

        admin_token = _env("ADMIN_TOKEN")
        ticket_secret = _env("TICKET_SECRET")
        if production and (not admin_token or not ticket_secret):
            raise RuntimeError(
                "production requires ADMIN_TOKEN and TICKET_SECRET environment variables"
            )
        if not ticket_secret:
            ticket_secret = secrets.token_urlsafe(32)
            LOGGER.warning("TICKET_SECRET missing; generated an ephemeral secret")
        if not admin_token:
            admin_token = secrets.token_urlsafe(24)
            LOGGER.warning("ADMIN_TOKEN missing; generated an ephemeral admin token")

        work_dir = Path(_env("N3M_WORK_DIR") or str(DEFAULT_WORK_DIR)).expanduser()
        if not work_dir.is_absolute():
            work_dir = (BACKEND_ROOT / work_dir).resolve()

        return cls(
            env=env,
            version="1.0.0",
            admin_token=admin_token,
            ticket_secret=ticket_secret,
            ticket_ttl_seconds=max(30, _env_int("TICKET_TTL_SECONDS", 300)),
            trusted_origins=_env_origins("TRUSTED_ORIGINS", DEFAULT_TRUSTED_ORIGINS),
            inspect_rate_per_min=max(1, _env_int("INSPECT_RATE_PER_MIN", 30)),
            download_rate_per_min=max(1, _env_int("DOWNLOAD_RATE_PER_MIN", 6)),
            admin_rate_per_min=max(1, _env_int("ADMIN_RATE_PER_MIN", 60)),
            max_concurrent_jobs=max(1, _env_int("MAX_CONCURRENT_JOBS", 2)),
            max_queued_jobs=max(1, _env_int("MAX_QUEUED_JOBS", 20)),
            job_timeout_seconds=max(60, _env_int("JOB_TIMEOUT_SECONDS", 1800)),
            job_retention_minutes=max(5, _env_int("JOB_RETENTION_MINUTES", 120)),
            min_free_gb=max(0.0, _env_float("MIN_FREE_GB", 2.0)),
            max_filesize_mb=max(1, _env_int("MAX_FILESIZE_MB", 2048)),
            max_url_length=max(32, _env_int("MAX_URL_LENGTH", 2048)),
            request_timeout_seconds=max(5, _env_int("REQUEST_TIMEOUT_SECONDS", 20)),
            trust_proxy=_env_bool("TRUST_PROXY_HEADERS", True),
            work_dir=work_dir,
            ytdlp_path=_env("YTDLP_BIN"),
            gallerydl_path=_env("GALLERYDL_BIN"),
            aria2c_path=_env("ARIA2C_BIN", "aria2c"),
            ffmpeg_path=_env("FFMPEG_BIN", "ffmpeg"),
            ytdlp_player_client=_env("YTDLP_PLAYER_CLIENT", "tv,mweb"),
        )

    def prepare_dirs(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)


def trusted_origins_from_env() -> tuple[str, ...]:
    """Origin allowlist without generating secrets (safe during app assembly)."""
    _load_dotenv(BACKEND_ROOT / ".env")
    return _env_origins("TRUSTED_ORIGINS", DEFAULT_TRUSTED_ORIGINS)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
