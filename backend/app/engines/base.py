"""Engine contracts and process helpers."""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings
from ..errors import EngineError

LOGGER = logging.getLogger("n3m.engines")


@dataclass(slots=True)
class EngineInfo:
    key: str
    available: bool
    version: str | None = None
    path: str | None = None


def module_available(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


def package_version(name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(name)
    except PackageNotFoundError:
        return None


async def run_process(
    command: list[str], *, timeout: float = 30.0
) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise EngineError("timeout", "انتهت مهلة المحرك.", " ".join(command)) from exc
    return process.returncode or 0, stdout, stderr


def tail(value: bytes, limit: int = 600) -> str:
    text = value.decode("utf-8", "replace").strip()
    return text[-limit:]


def python_module_command(settings: Settings, module: str, configured: str) -> list[str]:
    if configured:
        return [configured]
    executable = shutil.which(module.replace("_", "-"))
    if executable:
        return [executable]
    return [sys.executable, "-m", module]


def resolve_binary(configured: str) -> str | None:
    candidate = configured.strip() if configured else ""
    if candidate and (Path(candidate).is_file() or shutil.which(candidate)):
        return candidate
    return None
