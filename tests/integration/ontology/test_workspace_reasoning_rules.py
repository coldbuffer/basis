"""Workspace reasoning rule library routes."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_reasoning_rules_crud_and_isolation(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rules@example.com", "password": "password1", "display_name": "Rules"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Rules KB", "visibility": "restricted"},
    ).json()["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/rules",
        headers=headers,
        json={
            "name": "Drug candidate",
            "body": "IF inhibits(A, B) AND causes(B, C) THEN candidate(A, C)",
            "enabled": True,
        },
    )
    assert created.status_code == 200
    rule_id = created.json()["rule"]["id"]

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/rules", headers=headers)
    assert listed.status_code == 200
    assert any(r["id"] == rule_id for r in listed.json()["rules"])

    updated = client.patch(
        f"/api/v1/workspaces/{workspace_id}/rules/{rule_id}",
        headers=headers,
        json={"enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["rule"]["enabled"] is False

    deleted = client.delete(f"/api/v1/workspaces/{workspace_id}/rules/{rule_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/workspaces/{workspace_id}/rules", headers=headers).json()["rules"] == []

    other = client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password1", "display_name": "Other"},
    ).json()
    headers_b = {"Authorization": f"Bearer {other['token']}"}

    denied = client.get(f"/api/v1/workspaces/{workspace_id}/rules", headers=headers_b)
    assert denied.status_code == 403


def test_viewer_cannot_mutate_rules(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    owner = client.post(
        "/api/v1/auth/register",
        json={"email": "own@example.com", "password": "password1", "display_name": "Own"},
    ).json()
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    workspace_id = client.post(
        "/api/v1/workspaces",
        headers=owner_headers,
        json={"name": "Viewer Rules KB", "visibility": "restricted"},
    ).json()["id"]

    viewer = client.post(
        "/api/v1/auth/register",
        json={"email": "view@example.com", "password": "password1", "display_name": "View"},
    ).json()
    client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{viewer['user']['id']}",
        headers=owner_headers,
        json={"role": "viewer"},
    )
    viewer_headers = {"Authorization": f"Bearer {viewer['token']}"}

    assert (
        client.post(
            f"/api/v1/workspaces/{workspace_id}/rules",
            headers=viewer_headers,
            json={"name": "X", "body": "IF a THEN b", "enabled": True},
        ).status_code
        == 403
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/rules",
        headers=owner_headers,
        json={"name": "Y", "body": "IF c THEN d", "enabled": True},
    ).json()["rule"]["id"]

    assert (
        client.patch(
            f"/api/v1/workspaces/{workspace_id}/rules/{created}",
            headers=viewer_headers,
            json={"enabled": False},
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/workspaces/{workspace_id}/rules/{created}", headers=viewer_headers).status_code == 403
    )
