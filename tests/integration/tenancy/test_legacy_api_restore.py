"""Legacy mount when BASIS_LEGACY_API_ENABLED=1."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_legacy_workspaces_mount_when_enabled(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, legacy_api_enabled=True)))
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "legacy@example.com", "password": "password1", "display_name": "L"},
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    assert client.get("/api/v1/workspaces", headers=headers).status_code == 200
    legacy = client.get("/api/workspaces", headers=headers)
    assert legacy.status_code == 200
    assert legacy.headers.get("deprecation") == "true"
