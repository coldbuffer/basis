"""Workspace-scoped API tokens (graph access isolation)."""

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_workspace_api_token_reads_scoped_graph(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "tok@example.com", "password": "password1", "display_name": "T"},
    ).json()
    session = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=session).json()["workspaces"][0]["id"]
    other = client.post(
        "/api/v1/workspaces",
        headers=session,
        json={"name": "Other", "visibility": "restricted"},
    ).json()["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=session,
        json={"doc_id": "tok-doc", "text": "hello", "extract": False},
    )

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/tokens",
        headers=session,
        json={"name": "ci", "scope": "read"},
    )
    assert created.status_code == 200
    secret = created.json()["secret"]
    api_headers = {"Authorization": f"Bearer {secret}"}

    ok = client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=api_headers)
    assert ok.status_code == 200

    denied = client.get(f"/api/v1/workspaces/{other}/graph/stats", headers=api_headers)
    assert denied.status_code == 403

    listed = client.get(f"/api/v1/workspaces/{workspace_id}/tokens", headers=session).json()["tokens"]
    assert any(t["name"] == "ci" for t in listed)

    token_id = next(t["id"] for t in listed if t["name"] == "ci")
    revoked = client.delete(f"/api/v1/workspaces/{workspace_id}/tokens/{token_id}", headers=session)
    assert revoked.status_code == 200
    assert client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=api_headers).status_code == 401
