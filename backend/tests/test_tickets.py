from __future__ import annotations

import pytest

from app.tickets import TicketError, sign_ticket, verify_ticket

SECRET = "unit-test-secret"


def test_roundtrip():
    token = sign_ticket(SECRET, "job-1", ttl_seconds=300, now=1000)
    payload = verify_ticket(SECRET, token, now=1001)
    assert payload["j"] == "job-1"
    assert payload["e"] == 1300


def test_expired():
    token = sign_ticket(SECRET, "job-2", ttl_seconds=5, now=1000)
    with pytest.raises(TicketError) as exc:
        verify_ticket(SECRET, token, now=1006)
    assert exc.value.reason == "expired"


def test_tampered_job_id():
    token = sign_ticket(SECRET, "job-3", ttl_seconds=300, now=1000)
    body, signature = token.split(".")
    forged = sign_ticket(SECRET, "job-4", ttl_seconds=300, now=1000).split(".")[0]
    with pytest.raises(TicketError) as exc:
        verify_ticket(SECRET, f"{forged}.{signature}", now=1001)
    assert exc.value.reason == "invalid"


def test_wrong_secret():
    token = sign_ticket(SECRET, "job-5", ttl_seconds=300, now=1000)
    with pytest.raises(TicketError):
        verify_ticket("another-secret", token, now=1001)


@pytest.mark.parametrize("token", ["", "abc", "a.b.c", "!!!.???"])
def test_malformed(token):
    with pytest.raises(TicketError):
        verify_ticket(SECRET, token, now=1001)
