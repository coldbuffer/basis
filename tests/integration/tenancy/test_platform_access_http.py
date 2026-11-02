"""Platform ``GET/PUT /api/v1/settings/access`` (login providers, mail, URLs)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.app import create_app


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": "U"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_access_settings_requires_system_admin(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "access-admin@example.com")
    member = _register(client, "access-member@example.com")
    admin_headers = _auth(admin["token"])
    member_headers = _auth(member["token"])

    assert client.get("/api/v1/settings/access", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/settings/access", headers=member_headers).status_code == 403
    assert (
        client.put(
            "/api/v1/settings/access",
            headers=member_headers,
            json={"magic_link_dev_log": True},
        ).status_code
        == 403
    )


def test_access_settings_roundtrip_updates_auth_providers(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "access-round@example.com")
    headers = _auth(admin["token"])

    before = client.get("/api/v1/settings/access", headers=headers).json()
    assert "password" in before["auth_providers"]

    updated = client.put(
        "/api/v1/settings/access",
        headers=headers,
        json={
            "auth_providers": ["password", "email"],
            "magic_link_dev_log": True,
            "public_url": "http://api.basis.test",
            "web_origin": "http://app.basis.test",
            "credentials": {"email": {"from": "noreply@basis.test"}},
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["auth_providers"] == ["password", "email"]
    assert body["magic_link_dev_log"] is True
    assert body["public_url"] == "http://api.basis.test"
    assert body["web_origin"] == "http://app.basis.test"
    assert body["credentials"]["email"]["from"] == "noreply@basis.test"

    after = client.get("/api/v1/settings/access", headers=headers).json()
    assert after["auth_providers"] == ["password", "email"]
    assert after["public_url"] == "http://api.basis.test"


def test_access_settings_filters_unknown_auth_providers(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "access-filter@example.com")
    headers = _auth(admin["token"])

    put = client.put(
        "/api/v1/settings/access",
        headers=headers,
        json={"auth_providers": ["password", "not_a_provider", "email"]},
    )
    assert put.status_code == 200
    assert put.json()["auth_providers"] == ["password", "email"]
