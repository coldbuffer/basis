"""HTTP tests for connector OAuth app config (GET public metadata, PUT secret merge)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.app import create_app


def test_oauth_config_get_and_optional_secret_on_put(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "oauth@basis.local",
            "password": "password123",
            "display_name": "OAuth",
        },
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    base = f"/api/v1/workspaces/{workspace_id}/connectors/oauth-configs/github"

    missing = client.get(base, headers=headers)
    assert missing.status_code == 404

    put = client.put(
        base,
        headers=headers,
        json={
            "client_id": "gh_test_client",
            "client_secret": "gh_test_secret",
            "redirect_uri": "http://localhost/cb",
        },
    )
    assert put.status_code == 200

    got = client.get(base, headers=headers)
    assert got.status_code == 200
    public = got.json()["oauth_config"]
    assert public["client_id"] == "gh_test_client"
    assert public["has_client_secret"] is True
    assert "client_secret" not in public

    rotated_id = client.put(
        base,
        headers=headers,
        json={"client_id": "gh_rotated_client", "redirect_uri": "http://localhost/cb"},
    )
    assert rotated_id.status_code == 200
    assert rotated_id.json()["oauth_config"]["client_id"] == "gh_rotated_client"

    still = client.get(base, headers=headers)
    assert still.json()["oauth_config"]["has_client_secret"] is True
