import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_graph_survives_new_api_process(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)

    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "password": "password1", "display_name": "管理员"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    ingested = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "persist-doc", "text": "Alice works at Acme Corp.", "extract": False},
    )
    assert ingested.status_code == 200
    assert ingested.json()["node_count"] >= 1

    client2 = TestClient(create_app(settings))
    stats = client2.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["node_count"] >= 1

    docs = client2.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=headers)
    assert docs.status_code == 200
    ids = [item["doc_id"] for item in docs.json()["documents"]]
    assert "persist-doc" in ids
