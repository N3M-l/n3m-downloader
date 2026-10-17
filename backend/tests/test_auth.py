from __future__ import annotations

from tests.conftest import StubEngines


def test_inspect_requires_trusted_origin(client):
    response = client.post("/api/inspect", json={"url": "https://example.com/a.mp4"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_inspect_rejects_foreign_origin(client):
    response = client.post(
        "/api/inspect",
        json={"url": "https://example.com/a.mp4"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 401


def test_trusted_origin_passes_security(client, app, trusted_headers):
    class Local(StubEngines):
        async def inspect(self, url, platform_key=None):
            return await super().inspect(url, platform_key)

    app.state.engines = Local()
    response = client.post(
        "/api/inspect",
        json={"url": "https://www.youtube.com/watch?v=abc"},
        headers=trusted_headers,
    )
    assert response.status_code == 200


def test_trusted_origin_still_validates_url(client, trusted_headers):
    response = client.post(
        "/api/inspect",
        json={"url": "http://127.0.0.1/private"},
        headers=trusted_headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "blocked_host"


def test_admin_requires_token(client):
    response = client.get("/api/admin/status")
    assert response.status_code == 401


def test_admin_rejects_wrong_token(client):
    response = client.get(
        "/api/admin/status", headers={"Authorization": "Bearer wrong"}
    )
    assert response.status_code == 403


def test_admin_bearer_works_without_origin(client, admin_headers):
    response = client.get("/api/admin/status", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "online"
    assert "engines" in body and "disk" in body


def test_preflight_is_public(client):
    response = client.options(
        "/api/inspect",
        headers={
            "Origin": "https://n3m.fun",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code in {200, 204}


def test_security_headers_present(client):
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_unknown_ticket_is_rejected_without_origin(client):
    response = client.get("/api/download/not-a-ticket")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid"
