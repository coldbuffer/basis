"""Ledger chunk and document chunk listing."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore


def test_chunk_detail_and_document_chunks(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ch@example.com", "password": "password1", "display_name": "Ch"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="note.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="my-doc",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="Alice knows Bob here.")
    store.set_version_status(workspace_id, version_id, "ready")
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    bob = store.create_entity(workspace_id, canonical_label="Bob")
    store.add_open_statement(
        workspace_id,
        subject_id=alice,
        surface_phrase="knows",
        object_entity_id=bob,
        object_value=None,
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="knows Bob",
    )
    store.close()

    meta = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/documents/my-doc", headers=headers)
    assert meta.status_code == 200
    assert meta.json()["document"]["doc_id"] == "my-doc"

    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/documents/my-doc/chunks",
        headers=headers,
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["doc_ref"] == "my-doc"
    assert len(body["chunks"]) == 1
    assert body["chunks"][0]["id"] == chunk_id

    detail = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/chunks/{chunk_id}", headers=headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["chunk"]["chunk_id"] == chunk_id
    assert "Alice knows Bob" in detail_body["chunk"]["text"]
    assert len(detail_body["statements"]) == 1
    assert detail_body["statements"][0]["surface_phrase"] == "knows"
    assert detail_body["statements"][0]["quote"] == "knows Bob"
