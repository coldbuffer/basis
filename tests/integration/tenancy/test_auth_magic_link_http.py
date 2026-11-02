"""Magic-link request and verify over HTTP."""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.app import create_app


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_admin(client: TestClient) -> dict[str, str]:
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "magic-admin@example.com", "password": "password1", "display_name": "Admin"},
    )
    assert reg.status_code == 200, reg.text
    return _auth(reg.json()["token"])


def _enable_magic_link_dev_log(client: TestClient, admin_headers: dict[str, str]) -> None:
    updated = client.put(
        "/api/v1/settings/access",
        headers=admin_headers,
        json={
            "auth_providers": ["password", "email"],
            "magic_link_dev_log": True,
            "credentials": {"email": {"from": "noreply@magic.test"}},
        },
    )
    assert updated.status_code == 200, updated.text
    assert "email" in updated.json()["auth_providers"]


def _token_from_magic_link_log(caplog: pytest.LogCaptureFixture, email: str) -> str:
    pattern = re.compile(rf"Magic link for {re.escape(email)}: \S+\?token=([^\s]+)")
    for record in caplog.records:
        match = pattern.search(record.getMessage())
        if match:
            return match.group(1)
    raise AssertionError("magic link URL not found in logs")


def test_magic_link_request_and_verify_issues_session(tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    client = _client(tmp_path)
    admin_headers = _register_admin(client)
    _enable_magic_link_dev_log(client, admin_headers)

    email = "magic-user@example.com"
    with caplog.at_level(logging.INFO, logger="basis.services.tenancy.identity.magic_link"):
        requested = client.post("/api/v1/auth/magic-link/request", json={"email": email})
    assert requested.status_code == 200
    assert requested.json() == {"ok": True}

    token = _token_from_magic_link_log(caplog, email)
    verify = client.get(f"/api/v1/auth/magic-link/verify?token={token}", follow_redirects=False)
    assert verify.status_code == 302
    location = verify.headers["location"]
    assert "basis_token=" in location

    session = parse_qs(urlparse(location).query)["basis_token"][0]
    workspaces = client.get("/api/v1/workspaces", headers=_auth(session))
    assert workspaces.status_code == 200


def test_magic_link_verify_rejects_unknown_token(tmp_path) -> None:
    client = _client(tmp_path)
    admin_headers = _register_admin(client)
    _enable_magic_link_dev_log(client, admin_headers)

    response = client.get("/api/v1/auth/magic-link/verify?token=not-a-real-token", follow_redirects=False)
    assert response.status_code == 302
    assert "magic_link_error=invalid_token" in response.headers["location"]


def test_magic_link_request_not_available_without_email_provider(tmp_path) -> None:
    client = _client(tmp_path)
    admin_headers = _register_admin(client)

    only_password = client.put(
        "/api/v1/settings/access",
        headers=admin_headers,
        json={"auth_providers": ["password"], "magic_link_dev_log": True},
    )
    assert only_password.status_code == 200

    denied = client.post("/api/v1/auth/magic-link/request", json={"email": "x@example.com"})
    assert denied.status_code == 404
    assert denied.json()["detail"]["code"] == "not_configured"
