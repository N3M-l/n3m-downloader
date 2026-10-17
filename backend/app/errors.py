"""Typed API errors with Arabic, human-readable messages."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """An expected failure that maps to one JSON error response."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error": {"code": self.code, "message": self.message}
        }
        if self.details:
            body["error"]["details"] = self.details
        return body


class EngineError(Exception):
    """A media-engine failure; translated by the HTTP layer."""

    def __init__(self, code: str, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
