"""Graph import review staging and rejection."""

import json

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings


def test_reject_graph_import_deletes_staged_blob(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rej@example.com", "password": "password1", "display_name": "Rej"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    payload = {"nodes": [{"id": "n1", "type": "entity", "properties": {"content": "x"}}], "edges": []}
    files = {"file": ("graph.json", json.dumps(payload), "application/json")}
    proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/graph-import",
        headers=headers,
        files=files,
    )
    assert proposed.status_code == 200
    item = proposed.json()["item"]
    blob_key = item["payload"]["blob_key"]

    rejected = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{item['id']}/reject",
        headers=headers,
        json={"rationale": "no"},
    )
    assert rejected.status_code == 200

    from basis.services.knowledge.blob_store import BlobStore

    blobs = BlobStore(tmp_path)
    try:
        blobs.read(workspace_id, blob_key)
        assert False, "staged blob should be removed after reject"
    except Exception:
        pass


def test_approve_graph_import_deletes_staged_blob(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "app@example.com", "password": "password1", "display_name": "App"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    payload = {"nodes": [{"id": "n1", "type": "entity", "properties": {"content": "x"}}], "edges": []}
    files = {"file": ("graph.json", json.dumps(payload), "application/json")}
    proposed = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/graph-import",
        headers=headers,
        files=files,
    )
    assert proposed.status_code == 200
    item = proposed.json()["item"]
    blob_key = item["payload"]["blob_key"]

    approved = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{item['id']}/approve",
        headers=headers,
        json={"rationale": "ok"},
    )
    assert approved.status_code == 200

    from basis.services.knowledge.blob_store import BlobStore

    blobs = BlobStore(tmp_path)
    try:
        blobs.read(workspace_id, blob_key)
        assert False, "staged blob should be removed after approve"
    except Exception:
        pass
