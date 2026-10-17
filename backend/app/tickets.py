"""Short-lived HMAC-SHA256 download tickets.

The ticket only names a job; the file path always comes from the in-memory job
registry, so a forged path can never be expressed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

MAX_TOKEN_LENGTH = 2048


class TicketError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _signature(secret: str, payload: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def sign_ticket(
    secret: str,
    job_id: str,
    *,
    ttl_seconds: int = 300,
    now: float | None = None,
) -> str:
    issued = time.time() if now is None else now
    payload = {
        "j": job_id,
        "e": int(issued + ttl_seconds),
        "n": secrets.token_urlsafe(8),
    }
    body = _b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    )
    return f"{body}.{_signature(secret, body)}"


def verify_ticket(
    secret: str,
    token: str,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    if not token or len(token) > MAX_TOKEN_LENGTH or token.count(".") != 1:
        raise TicketError("invalid", "رابط التحميل غير صالح.")
    body, signature = token.split(".", 1)
    expected = _signature(secret, body)
    if not hmac.compare_digest(signature, expected):
        raise TicketError("invalid", "رابط التحميل غير صالح.")
    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TicketError("invalid", "رابط التحميل غير صالح.") from exc
    if not isinstance(payload, dict):
        raise TicketError("invalid", "رابط التحميل غير صالح.")
    job_id = payload.get("j")
    expires = payload.get("e")
    if not isinstance(job_id, str) or not isinstance(expires, (int, float)):
        raise TicketError("invalid", "رابط التحميل غير صالح.")
    current = time.time() if now is None else now
    if current >= float(expires):
        raise TicketError("expired", "انتهت صلاحية رابط التحميل. أعد المحاولة.")
    return payload
