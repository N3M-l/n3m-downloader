"""Regression tests for YouTube proxy failure and verification reporting."""
from __future__ import annotations

import asyncio
import pytest

from app.config import Settings
from app.engines.ytdlp import (
    YtDlpEngine,
    _failure_message,
    _proxy_connection_failed,
    _youtube_verification_required,
)
from app.errors import EngineError


def test_proxy_failure_detected_without_masking_youtube_bot_check():
    assert _proxy_connection_failed(
        "Failed to connect to www.youtube.com:443 over proxy 127.0.0.1: Could not connect to server"
    )
    assert not _proxy_connection_failed("Sign in to confirm you're not a bot")
    assert not _proxy_connection_failed("HTTP Error 403: Forbidden")


def test_youtube_verification_message():
    detail = "Sign in to confirm you're not a bot"
    assert _youtube_verification_required(detail)
    assert "يوتيوب" in _failure_message(detail, "generic")


def test_inspect_retries_direct_when_proxy_connection_fails(settings: Settings, monkeypatch):
    engine = YtDlpEngine(settings)
    monkeypatch.setattr(engine, "available", lambda: True)
    monkeypatch.setattr(engine, "proxy_args", lambda url: ["--proxy", "socks5://127.0.0.1:8086"])
    monkeypatch.setattr(engine, "impersonation_args", lambda: [])
    monkeypatch.setattr(engine, "extractor_args", lambda: [])
    monkeypatch.setattr(engine, "cookies_args", lambda: [])
    commands = []

    async def fake_run(command, *, timeout):
        commands.append(command)
        if "--proxy" in command:
            return 1, b"", b"Failed to connect over proxy 127.0.0.1: Could not connect"
        return 0, b'{"title":"Test video","formats":[]}', b""

    monkeypatch.setattr("app.engines.ytdlp.run_process", fake_run)
    result = asyncio.run(engine.inspect("https://www.youtube.com/watch?v=test"))
    assert result["title"] == "Test video"
    assert len(commands) == 2
    assert "--proxy" in commands[0]
    assert "--proxy" not in commands[1]


def test_inspect_does_not_retry_bot_denial(settings: Settings, monkeypatch):
    engine = YtDlpEngine(settings)
    monkeypatch.setattr(engine, "available", lambda: True)
    monkeypatch.setattr(engine, "proxy_args", lambda url: ["--proxy", "socks5://127.0.0.1:8086"])
    monkeypatch.setattr(engine, "impersonation_args", lambda: [])
    monkeypatch.setattr(engine, "extractor_args", lambda: [])
    monkeypatch.setattr(engine, "cookies_args", lambda: [])
    commands = []

    async def fake_run(command, *, timeout):
        commands.append(command)
        return 1, b"", b"Sign in to confirm you're not a bot"

    monkeypatch.setattr("app.engines.ytdlp.run_process", fake_run)
    with pytest.raises(EngineError) as exc:
        asyncio.run(engine.inspect("https://www.youtube.com/watch?v=test"))
    assert exc.value.code == "youtube_verification_required"
    assert len(commands) == 1
