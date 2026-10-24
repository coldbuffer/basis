"""Hard delete document, chunks, ledger rows, and graph projection."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_delete_document_removes_chunks_and_graph_node(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "del@example.com", "password": "password1", "display_name": "Del"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "to-delete", "text": "Alice knows Bob in this note."},
    )
    assert created.status_code == 200
    body = created.json()
    document_id = body["document_id"]
    version_id = body["version_id"]

    processed = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={
            "version_id": version_id,
            "wait": True,
            "chunk": False,
            "extract": True,
            "ner_method": "llm",
            "relation_method": "llm",
        },
    )
    assert processed.status_code == 200
    assert processed.json()["ledger_status"] == "ready"

    chunks_before = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/documents/to-delete/chunks",
        headers=headers,
    )
    assert chunks_before.status_code == 200
    assert len(chunks_before.json()["chunks"]) >= 1

    stats = client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=headers)
    assert stats.status_code == 200
    nodes_before = stats.json().get("node_count", 0)
    assert nodes_before >= 1

    deleted = client.delete(
        f"/api/v1/workspaces/{workspace_id}/documents/{document_id}",
        headers=headers,
    )
    assert deleted.status_code == 200
    payload = deleted.json()
    assert payload["ok"] is True
    assert payload["chunk_ids"]

    docs = client.get(f"/api/v1/workspaces/{workspace_id}/documents", headers=headers).json()["documents"]
    assert not any(d.get("doc_id") == "to-delete" for d in docs)

    chunks_after = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/documents/to-delete/chunks",
        headers=headers,
    )
    assert chunks_after.status_code == 404

    stats_after = client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=headers).json()
    assert stats_after.get("node_count", 0) < nodes_before


def test_delete_document_rejects_active_processing(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path, ingest_inline=False),
    )
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "busy@example.com", "password": "password1", "display_name": "Busy"},
    ).json()
    headers = _auth(admin["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "busy-doc", "text": "Processing soon."},
    ).json()

    queued = client.post(
        f"/api/v1/workspaces/{workspace_id}/processing/jobs",
        headers=headers,
        json={"version_id": created["version_id"], "wait": False},
    )
    assert queued.status_code in (200, 202)

    denied = client.delete(
        f"/api/v1/workspaces/{workspace_id}/documents/{created['document_id']}",
        headers=headers,
    )
    assert denied.status_code == 409
