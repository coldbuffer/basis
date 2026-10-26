from pathlib import Path

from fastapi.testclient import TestClient

from basis.domain.graph.projection.session import GraphSession
from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings


def test_archive_graph_node_http(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "arch@example.com", "password": "password1", "display_name": "A"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    node_id = "archive-test-node"
    session = GraphSession()
    session.add_node(node_id, "entity", content="Archive Me")
    persistence = client.app.state.graph_persistence
    client.app.state.graphs[workspace_id] = session
    persistence.save(workspace_id, session, projection_revision=1, schema_version=1)

    deleted = client.delete(
        f"/api/v1/workspaces/{workspace_id}/graph/nodes/{node_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    body = deleted.json()
    assert body.get("status") == "archived"
    assert body.get("node_id") == node_id
