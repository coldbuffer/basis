"""``connectors_embed`` HTTP routes (``/workspaces/{id}/connectors/embed/*``)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from basis.infra.runtime.config import Settings
from basis.app import create_app


def _auth_client(tmp_path: Path) -> tuple[TestClient, str, dict[str, str]]:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "embed@basis.local",
            "password": "password123",
            "display_name": "Embed",
        },
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0][
        "id"
    ]
    return client, workspace_id, headers


def test_embed_providers_and_qq_mail_connection(tmp_path: Path) -> None:
    client, workspace_id, headers = _auth_client(tmp_path)
    prov = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/embed/providers",
        headers=headers,
        params={"has_streams_only": False},
    )
    assert prov.status_code == 200
    services = {p["service"] for p in prov.json()["providers"]}
    assert "qq_mail" in services

    put = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/embed/connections/qq_mail",
        headers=headers,
        json={
            "subject_id": "embed-subject-1",
            "auth_type": "custom",
            "credentials": {
                "email": "u@qq.com",
                "authorizationCode": "abcdefghijklmnop",
            },
        },
    )
    assert put.status_code == 200
    conn = put.json()["connection"]
    assert conn["connection_scope"] == "end_user"
    assert conn["subject_id"] == "embed-subject-1"

    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/embed/connections",
        headers=headers,
        params={"subject_id": "embed-subject-1"},
    )
    assert listed.status_code == 200
    assert len(listed.json()["connections"]) == 1

    deleted = client.delete(
        f"/api/v1/workspaces/{workspace_id}/connectors/embed/connections/qq_mail",
        headers=headers,
        params={"subject_id": "embed-subject-1"},
    )
    assert deleted.status_code == 200


def test_invoke_primitive_http_uses_end_user_scope(tmp_path: Path) -> None:
    """ROADMAP phase 1: invoke via workspace route + ``connection_scope`` / ``subject_id``."""
    client, workspace_id, headers = _auth_client(tmp_path)
    subject = "embed-subject-invoke"
    put = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/embed/connections/qq_mail",
        headers=headers,
        json={
            "subject_id": subject,
            "auth_type": "custom",
            "credentials": {
                "email": "u@qq.com",
                "authorizationCode": "abcdefghijklmnop",
            },
        },
    )
    assert put.status_code == 200

    with patch(
        "basis.routes.workspace.connector.connections.op_invoke_connector_primitive",
        return_value={"records": []},
    ) as invoke:
        resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/connectors/connections/qq_mail/invoke-primitive",
            headers=headers,
            json={
                "action_id": "messages",
                "primitive": "list",
                "connection_scope": "end_user",
                "subject_id": subject,
            },
        )
    assert resp.status_code == 200
    args = invoke.call_args[0][1]
    assert args["connection_scope"] == "end_user"
    assert args["subject_id"] == subject
