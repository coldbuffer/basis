"""Governance config HTTP routes."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app


def test_governance_config_get_put(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "gc@example.com", "password": "password1", "display_name": "GC"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    get0 = client.get(f"/api/v1/workspaces/{workspace_id}/governance/config", headers=headers)
    assert get0.status_code == 200
    assert get0.json()["config"]["governor_enabled"] is False

    put = client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": True,
            "governor_interval_minutes": 120,
            "governor_confidence_min": 0.6,
        },
    )
    assert put.status_code == 200
    body = put.json()["config"]
    assert body["governor_enabled"] is True
    assert body["governor_interval_minutes"] == 120
    assert body["governor_confidence_min"] == 0.6
    assert "entity_type_surface_phrases" in body
    assert "是" in body["entity_type_surface_phrases"]

    put_phrases = client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": True,
            "governor_interval_minutes": 120,
            "governor_confidence_min": 0.6,
            "entity_type_surface_phrases": ["typed_as", "是"],
        },
    )
    assert put_phrases.status_code == 200
    phrases = put_phrases.json()["config"]["entity_type_surface_phrases"]
    assert phrases == ["typed_as", "是"]
