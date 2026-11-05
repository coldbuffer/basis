import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_graph_snapshot_lists_document_after_ingest(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "g@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "snap-doc", "text": "hello graph", "extract": False},
    )

    snap = client.get(f"/api/v1/workspaces/{workspace_id}/graph/snapshot", headers=headers)
    assert snap.status_code == 200
    body = snap.json()
    assert body["stats"]["node_count"] >= 1
    ids = [n["id"] for n in body["nodes"]]
    assert "snap-doc" in ids


def test_graph_projection_and_rebuild_audit(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "p@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "proj-doc", "text": "projection test", "extract": False},
    )

    projection = client.get(f"/api/v1/workspaces/{workspace_id}/graph/projection", headers=headers)
    assert projection.status_code == 200
    proj_body = projection.json()
    assert "revision" in proj_body
    assert "status" in proj_body
    assert proj_body.get("node_count", 0) >= 1

    rebuild = client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers)
    assert rebuild.status_code == 200
    assert "projection_revision" in rebuild.json()

    audit = client.get(f"/api/v1/audit?workspace_id={workspace_id}", headers=headers)
    assert audit.status_code == 200
    actions = [e["action"] for e in audit.json()["events"]]
    assert "workspace.graph.projection_rebuild" in actions

    workspace_audit = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/graph-mutations?action_prefix=workspace.graph.",
        headers=headers,
    )
    assert workspace_audit.status_code == 200
    workspace_actions = [e["action"] for e in workspace_audit.json()["events"]]
    assert "workspace.graph.projection_rebuild" in workspace_actions


def test_workspace_graph_audit_visible_to_viewer_not_platform_audit(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    owner = client.post(
        "/api/v1/auth/register",
        json={"email": "own@example.com", "password": "password1", "display_name": "O"},
    ).json()
    owner_headers = _auth(owner["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=owner_headers).json()["workspaces"][0]["id"]

    viewer = client.post(
        "/api/v1/auth/register",
        json={"email": "view@example.com", "password": "password1", "display_name": "V"},
    ).json()
    viewer_id = client.get("/api/v1/users", headers=owner_headers).json()["users"]
    viewer_user = next(u for u in viewer_id if u["email"] == "view@example.com")
    client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{viewer_user['id']}",
        headers=owner_headers,
        json={"role": "viewer"},
    )
    viewer_headers = _auth(viewer["token"])

    client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=owner_headers)

    denied = client.get("/api/v1/audit", headers=viewer_headers)
    assert denied.status_code == 403

    allowed = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/graph-mutations",
        headers=viewer_headers,
    )
    assert allowed.status_code == 200


def test_platform_reports_capabilities(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    info = client.get("/api/v1/platform").json()
    assert info["capabilities"]["graph_snapshot"] is True
    assert isinstance(info["capabilities"]["graph_runtime"], bool)
