"""Graph pagination server caps."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.infra.runtime.limits import GRAPH_PAGE_MAX_EDGES, GRAPH_PAGE_MAX_NODES


def test_graph_nodes_limit_capped(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "lim@example.com", "password": "password1", "display_name": "Lim"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    res = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/nodes?limit=9999",
        headers=headers,
    )
    assert res.status_code == 200
    # Empty graph still returns; cap is applied inside paginator (no over-fetch crash).
    assert res.json()["engine"] in ("explorer", "snapshot")
    assert GRAPH_PAGE_MAX_NODES == 200


def test_graph_snapshot_limits_capped(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "snap@example.com", "password": "password1", "display_name": "Snap"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    res = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/snapshot?limit_nodes=99999&limit_edges=99999",
        headers=headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["nodes"]) <= GRAPH_PAGE_MAX_NODES
    assert len(body["edges"]) <= GRAPH_PAGE_MAX_EDGES
    assert body["truncated"]["nodes"] is False
    assert body["truncated"]["edges"] is False
