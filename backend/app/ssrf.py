"""SSRF protection: only public HTTP(S) destinations may be fetched.

Every user-supplied URL is resolved and every address must be globally
routable. Redirects are validated one hop at a time by direct fetchers.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from .config import REDIRECT_STATUSES, USER_AGENT
from .errors import ApiError

LOGGER = logging.getLogger("n3m.ssrf")

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
}
BLOCKED_SUFFIXES = (
    ".localhost",
    ".local",
    ".localdomain",
    ".internal",
    ".home.arpa",
    ".lan",
    ".intranet",
)
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_PORTS = {80, 443}
MAX_URL_LENGTH = 2048
MAX_REDIRECTS = 5


@dataclass(frozen=True, slots=True)
class ValidatedURL:
    url: str
    host: str
    port: int
    addresses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HeadInfo:
    url: str
    status_code: int
    content_type: str
    content_length: int | None
    filename: str | None


def _blocked(message: str = "هذا الرابط يشير إلى شبكة داخلية محظورة لحماية الخادم.") -> ApiError:
    return ApiError(400, "blocked_host", message)


def _invalid(message: str = "الرابط غير صالح. تأكد من كتابته بشكل صحيح.") -> ApiError:
    return ApiError(400, "invalid_url", message)


def _is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return False
    return address.is_global


def _resolve(host: str, port: int) -> tuple[str, ...]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError, OSError) as exc:
        LOGGER.info("DNS lookup failed for %s: %s", host, exc)
        raise _invalid("تعذّر العثور على هذا النطاق. تحقّق من الرابط أو اتصال الإنترنت.") from exc
    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise _invalid("تعذّر العثور على هذا النطاق. تحقّق من الرابط.")
    return tuple(addresses)


def validate_public_url(raw: str, *, allow_any_port: bool = False) -> ValidatedURL:
    """Validate scheme, host, port and every resolved address."""
    if not isinstance(raw, str):
        raise _invalid()
    value = raw.strip()
    if not value or len(value) > MAX_URL_LENGTH:
        raise _invalid("الرابط طويل جدًا أو فارغ.")
    if any(ord(char) < 32 for char in value):
        raise _invalid()

    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise _invalid() from exc

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise _invalid("يُسمح فقط بروابط HTTP و HTTPS.")
    if parts.username is not None or parts.password is not None:
        raise _invalid("الروابط التي تحتوي على بيانات دخول غير مسموحة.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise _invalid()

    if host in BLOCKED_HOSTNAMES or any(host.endswith(suffix) for suffix in BLOCKED_SUFFIXES):
        raise _blocked()

    if port is None:
        port = 443 if scheme == "https" else 80
    if not allow_any_port and port not in ALLOWED_PORTS:
        raise _invalid("يُسمح فقط بمنفذي 80 و 443.")

    # IP literal: validate directly, no DNS lookup.
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public_address(str(literal)):
            raise _blocked()
        addresses = (str(literal),)
    else:
        addresses = _resolve(host, port)
        if any(not _is_public_address(address) for address in addresses):
            LOGGER.warning("blocked host %s resolving to %s", host, addresses)
            raise _blocked()

    return ValidatedURL(url=value, host=host, port=port, addresses=addresses)


def _filename_from_disposition(value: str | None) -> str | None:
    if not value:
        return None
    extended = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", value, flags=re.IGNORECASE)
    if extended:
        from urllib.parse import unquote

        try:
            return unquote(extended.group(1).strip().strip('"'))
        except Exception:  # pragma: no cover - defensive
            return None
    simple = re.search(r'filename\s*=\s*"([^"]+)"', value, flags=re.IGNORECASE)
    if simple:
        return simple.group(1)
    simple = re.search(r"filename\s*=\s*([^;]+)", value, flags=re.IGNORECASE)
    if simple:
        return simple.group(1).strip()
    return None


def _total_from_content_range(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"/(\d+)\s*$", value)
    if match:
        return int(match.group(1))
    return None


async def safe_head(url: str, timeout: int = 15) -> HeadInfo:
    """HEAD (or range GET) with per-hop SSRF validation."""
    current = url
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout), follow_redirects=False, headers=headers
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            validated = await asyncio.to_thread(validate_public_url, current)
            try:
                response = await client.head(validated.url)
                if response.status_code in {405, 403, 400, 501}:
                    response = await client.get(
                        validated.url, headers={"Range": "bytes=0-0"}
                    )
            except httpx.HTTPError as exc:
                raise ApiError(
                    502,
                    "fetch_failed",
                    "تعذّر الوصول إلى هذا الرابط. تحقّق من اتصال الخادم بالإنترنت.",
                ) from exc
            if response.status_code in REDIRECT_STATUSES:
                location = response.headers.get("location")
                if not location:
                    raise ApiError(502, "fetch_failed", "أعاد الخادم تحويلًا غير مكتمل.")
                current = urljoin(current, location)
                continue
            if response.status_code >= 400:
                raise ApiError(
                    502,
                    "fetch_failed",
                    "تعذّر الوصول إلى هذا الملف. قد يكون محذوفًا أو محميًا.",
                )
            length = None
            raw_length = response.headers.get("content-length")
            if raw_length and raw_length.isdigit():
                length = int(raw_length)
            if response.status_code == 206:
                length = _total_from_content_range(response.headers.get("content-range"))
            return HeadInfo(
                url=current,
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                content_length=length,
                filename=_filename_from_disposition(
                    response.headers.get("content-disposition")
                ),
            )
    raise ApiError(400, "too_many_redirects", "الرابط يعيد التوجيه مرات كثيرة جدًا.")
