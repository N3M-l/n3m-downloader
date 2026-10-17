from __future__ import annotations

import os
import time
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import StubEngines


def wait_for(client, job_id: str, headers: dict, timeout: float = 6.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"completed", "failed", "cancelled"}:
            return body
        time.sleep(0.03)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


def test_inspect_response_shape(client, app, trusted_headers):
    app.state.engines = StubEngines()
    response = client.post(
        "/api/inspect",
        json={"url": "https://www.youtube.com/watch?v=abc"},
        headers=trusted_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "youtube"
    assert body["platformLabel"] == "YouTube"
    assert body["suggestedMode"] == "video"
    assert body["formats"][0]["id"] == "best"
    assert body["expiresAt"] > time.time() * 1000


def test_inspect_validation_error(client, trusted_headers):
    response = client.post("/api/inspect", json={}, headers=trusted_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_download_lifecycle_and_ticket(client, app, trusted_headers):
    app.state.engines = StubEngines(content=b"hello-n3m")
    response = client.post(
        "/api/download",
        json={"url": "https://www.youtube.com/watch?v=abc", "mode": "video"},
        headers=trusted_headers,
    )
    assert response.status_code == 202
    job_id = response.json()["jobId"]
    assert response.json()["pollUrl"] == f"/api/jobs/{job_id}"

    final = wait_for(client, job_id, trusted_headers)
    assert final["status"] == "completed", final
    assert final["progress"] == 100.0
    assert final["filename"] == "demo.mp4"
    assert final["downloadPath"].startswith("/api/download/")

    file_response = client.get(final["downloadPath"])
    assert file_response.status_code == 200
    assert file_response.content == b"hello-n3m"
    assert "demo.mp4" in file_response.headers.get("content-disposition", "")


def test_download_rejects_private_url(client, trusted_headers):
    response = client.post(
        "/api/download",
        json={"url": "http://169.254.169.254/latest/meta-data", "mode": "file"},
        headers=trusted_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "blocked_host"


def test_download_rejects_bad_mode(client, trusted_headers):
    response = client.post(
        "/api/download",
        json={"url": "https://example.com/a.mp4", "mode": "hack"},
        headers=trusted_headers,
    )
    assert response.status_code == 400


def test_events_endpoint_returns_sse(client, app, trusted_headers):
    app.state.engines = StubEngines(content=b"abc")
    response = client.post(
        "/api/download",
        json={"url": "https://example.com/a.mp4", "mode": "file"},
        headers=trusted_headers,
    )
    job_id = response.json()["jobId"]
    wait_for(client, job_id, trusted_headers)
    stream = client.get(f"/api/jobs/{job_id}/events", headers=trusted_headers)
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "data:" in stream.text
    assert "event: end" in stream.text


def test_cancel_running_job(client, app, trusted_headers):
    app.state.engines = StubEngines(delay=0.4)
    response = client.post(
        "/api/download",
        json={"url": "https://example.com/a.mp4", "mode": "file"},
        headers=trusted_headers,
    )
    job_id = response.json()["jobId"]
    cancel = client.post(f"/api/jobs/{job_id}/cancel", headers=trusted_headers)
    assert cancel.status_code == 200
    final = wait_for(client, job_id, trusted_headers)
    assert final["status"] == "cancelled"


def test_inspect_rate_limit(settings, trusted_headers):
    limited = replace(settings, inspect_rate_per_min=1)
    app = create_app(limited)
    with TestClient(app) as client:
        app.state.engines = StubEngines()
        first = client.post(
            "/api/inspect",
            json={"url": "https://www.youtube.com/watch?v=a"},
            headers=trusted_headers,
        )
        second = client.post(
            "/api/inspect",
            json={"url": "https://www.youtube.com/watch?v=b"},
            headers=trusted_headers,
        )
    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["retry-after"]) >= 1
    assert second.json()["error"]["code"] == "rate_limited"


def test_download_quota_guard(settings, trusted_headers):
    tight = replace(settings, min_free_gb=10**9)
    app = create_app(tight)
    app.state.engines = StubEngines()
    with TestClient(app) as client:
        response = client.post(
            "/api/download",
            json={"url": "https://example.com/a.mp4", "mode": "file"},
            headers=trusted_headers,
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "quota_exceeded"


def test_admin_cleanup_removes_old_jobs(client, settings, admin_headers):
    old = Path(settings.jobs_dir) / "old-job"
    old.mkdir(parents=True, exist_ok=True)
    (old / "junk.bin").write_bytes(b"x" * 128)
    past = time.time() - 4 * 3600
    os.utime(old, (past, past))
    response = client.post("/api/admin/cleanup", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["removedJobs"] >= 1
    assert body["freedBytes"] >= 128
    assert not old.exists()


def test_unknown_job_returns_404(client, trusted_headers):
    response = client.get("/api/jobs/deadbeef", headers=trusted_headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
