"""Workspace capability endpoint (Explorer integration design §12)."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available, workspace_capabilities
from basis.infra.runtime.config import Settings


def test_workspace_capabilities_unit_viewer_vs_editor() -> None:
    viewer = workspace_capabilities("viewer")
    owner = workspace_capabilities("owner")
    assert viewer["graph_write"] is False
    assert owner["graph_write"] is True
    if graph_runtime_available():
        assert viewer["import_export"] is False
        assert owner["import_export"] is True
        assert viewer["sparql"] is True


def test_workspace_capabilities_http(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "cap@example.com", "password": "password1", "display_name": "Cap"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    response = client.get(f"/api/v1/workspaces/{workspace_id}/capabilities", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["workspace_id"] == workspace_id
    assert body["role"] == "owner"
    assert body["graph_write"] is True
    assert body["graph_runtime"] == graph_runtime_available()
    assert "sparql" in body and "decisions" in body
    assert body["upload_max_bytes"] > 0
    assert body["ingest_max_inflight"] >= 1
    assert body["processing_job_timeout_seconds"] >= 60
