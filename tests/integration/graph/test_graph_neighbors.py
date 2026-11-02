import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_neighbors_and_path_on_document_node(tmp_path) -> None:
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
        json={"doc_id": "path-doc", "text": "hello", "extract": False},
    )

    neighbors = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/nodes/path-doc/neighbors",
        headers=headers,
    )
    assert neighbors.status_code == 200
    assert neighbors.json()["node_id"] == "path-doc"

    path = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/path",
        headers=headers,
        params={"source": "path-doc", "target": "path-doc"},
    )
    assert path.status_code == 200
    assert path.json()["found"] is True
