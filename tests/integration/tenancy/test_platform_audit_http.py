"""Platform ``GET /api/v1/audit`` (system admin)."""

from __future__ import annotations

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from basis.app import create_app


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": email.split("@")[0]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_platform_audit_requires_system_admin(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "audit-admin@example.com")
    member = _register(client, "audit-member@example.com")

    ok = client.get("/api/v1/audit", headers=_auth(admin["token"]))
    assert ok.status_code == 200
    assert "events" in ok.json()

    denied = client.get("/api/v1/audit", headers=_auth(member["token"]))
    assert denied.status_code == 403


def test_platform_audit_action_prefix_and_limit(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "audit-filter@example.com")
    headers = _auth(admin["token"])

    saved = client.put(
        "/api/v1/settings",
        headers=headers,
        json={"chat_model": "audit-filter-model"},
    )
    assert saved.status_code == 200

    settings_events = client.get(
        "/api/v1/audit",
        headers=headers,
        params={"action_prefix": "settings.", "limit": 5},
    )
    assert settings_events.status_code == 200
    events = settings_events.json()["events"]
    assert len(events) <= 5
    assert events
    assert all(e["action"].startswith("settings.") for e in events)
    assert any(e["action"] == "settings.updated" for e in events)

    capped = client.get("/api/v1/audit", headers=headers, params={"limit": 1})
    assert capped.status_code == 200
    assert len(capped.json()["events"]) == 1


def test_platform_audit_workspace_id_filter(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = _client(tmp_path)
    admin = _register(client, "audit-ws@example.com")
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    rebuild = client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers)
    assert rebuild.status_code == 200

    scoped = client.get(
        "/api/v1/audit",
        headers=headers,
        params={
            "workspace_id": workspace_id,
            "action_prefix": "workspace.graph.",
            "limit": 20,
        },
    )
    assert scoped.status_code == 200
    actions = [e["action"] for e in scoped.json()["events"]]
    assert "workspace.graph.projection_rebuild" in actions
    assert all(a.startswith("workspace.graph.") for a in actions)
