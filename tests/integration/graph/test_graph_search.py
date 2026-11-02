import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_graph_search_finds_document_node(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "s@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "find-me", "text": "unique token alpha", "extract": False},
    )

    found = client.post(
        f"/api/v1/workspaces/{workspace_id}/graph/search",
        headers=headers,
        json={"query": "find-me", "limit": 10},
    )
    assert found.status_code == 200
    body = found.json()
    assert body["results"]
    ids = [r["node"]["id"] for r in body["results"]]
    assert "find-me" in ids
