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
    assert get0.json()["config"]["vocabulary_alignment_requires_review"] is False

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
    assert "entity_type_surface_phrases" not in body

    put_review = client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": True,
            "governor_interval_minutes": 120,
            "governor_confidence_min": 0.6,
            "vocabulary_alignment_requires_review": True,
        },
    )
    assert put_review.status_code == 200
    assert put_review.json()["config"]["vocabulary_alignment_requires_review"] is True

    put_preserve = client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/config",
        headers=headers,
        json={
            "governor_enabled": False,
            "governor_interval_minutes": 60,
            "governor_confidence_min": 0.5,
        },
    )
    assert put_preserve.status_code == 200
    assert put_preserve.json()["config"]["vocabulary_alignment_requires_review"] is True

    get_interp = client.get(
        f"/api/v1/workspaces/{workspace_id}/governance/interpretation",
        headers=headers,
    )
    assert get_interp.status_code == 200
    phrases0 = get_interp.json()["interpretation"]["entity_type_surface_phrases"]
    assert "是" in phrases0

    put_phrases = client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/interpretation",
        headers=headers,
        json={"entity_type_surface_phrases": ["typed_as", "是"]},
    )
    assert put_phrases.status_code == 200
    phrases = put_phrases.json()["interpretation"]["entity_type_surface_phrases"]
    assert phrases == ["typed_as", "是"]
