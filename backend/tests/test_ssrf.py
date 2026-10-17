from __future__ import annotations

import socket

import pytest

from app.errors import ApiError
from app.ssrf import validate_public_url


def fake_dns(addresses: list[str]):
    def resolver(host, port, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
            for address in addresses
        ]

    return resolver


def test_public_ipv4_allowed(monkeypatch):
    monkeypatch.setattr("app.ssrf.socket.getaddrinfo", fake_dns(["93.184.216.34"]))
    result = validate_public_url("https://example.com/video.mp4")
    assert result.host == "example.com"
    assert result.port == 443
    assert result.addresses == ("93.184.216.34",)


def test_private_ipv4_blocked(monkeypatch):
    monkeypatch.setattr("app.ssrf.socket.getaddrinfo", fake_dns(["10.0.0.5"]))
    with pytest.raises(ApiError) as exc:
        validate_public_url("https://internal.example.com")
    assert exc.value.code == "blocked_host"


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "172.16.0.9", "192.168.1.1", "169.254.169.254", "0.0.0.0"],
)
def test_private_literals_blocked(address):
    with pytest.raises(ApiError) as exc:
        validate_public_url(f"http://{address}/file.mp4")
    assert exc.value.code == "blocked_host"


def test_ipv6_loopback_blocked():
    with pytest.raises(ApiError):
        validate_public_url("http://[::1]/file.mp4")


def test_localhost_name_blocked():
    with pytest.raises(ApiError) as exc:
        validate_public_url("http://localhost:443/file.mp4")
    assert exc.value.code == "blocked_host"


def test_ftp_scheme_rejected():
    with pytest.raises(ApiError) as exc:
        validate_public_url("ftp://example.com/file.mp4")
    assert exc.value.code == "invalid_url"


def test_userinfo_rejected():
    with pytest.raises(ApiError) as exc:
        validate_public_url("https://user:pass@example.com/file.mp4")
    assert exc.value.code == "invalid_url"


def test_unusual_port_rejected(monkeypatch):
    monkeypatch.setattr("app.ssrf.socket.getaddrinfo", fake_dns(["93.184.216.34"]))
    with pytest.raises(ApiError) as exc:
        validate_public_url("https://example.com:8080/file.mp4")
    assert exc.value.code == "invalid_url"


def test_mixed_public_private_blocked(monkeypatch):
    monkeypatch.setattr(
        "app.ssrf.socket.getaddrinfo", fake_dns(["93.184.216.34", "10.0.0.7"])
    )
    with pytest.raises(ApiError) as exc:
        validate_public_url("https://rebind.example.com")
    assert exc.value.code == "blocked_host"


def test_dns_failure_is_invalid(monkeypatch):
    def failure(*args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr("app.ssrf.socket.getaddrinfo", failure)
    with pytest.raises(ApiError) as exc:
        validate_public_url("https://does-not-exist.example")
    assert exc.value.code == "invalid_url"


def test_long_url_rejected():
    with pytest.raises(ApiError):
        validate_public_url("https://example.com/" + "a" * 3000)


def test_control_character_rejected():
    with pytest.raises(ApiError):
        validate_public_url("https://example.com/a\x00b")
