"""Ledger entity search and facts API."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore


def test_find_entities_and_facts(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ent@example.com", "password": "password1", "display_name": "Ent"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="d.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="d1",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="Alice knows Bob.")
    store.set_version_status(workspace_id, version_id, "ready")
    alice = store.create_entity(workspace_id, canonical_label="Alice Search")
    bob = store.create_entity(workspace_id, canonical_label="Bob")
    statement_id = store.add_open_statement(
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

    found = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities?query=Alice",
        headers=headers,
    )
    assert found.status_code == 200
    entities = found.json()["entities"]
    assert len(entities) >= 1
    assert entities[0]["id"] == alice
    assert entities[0]["entity_id"] == alice

    facts = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{alice}/facts",
        headers=headers,
    )
    assert facts.status_code == 200
    body = facts.json()
    assert body["entity_id"] == alice
    assert len(body["facts"]) == 1
    assert body["facts"][0]["surface_phrase"] == "knows"
    assert body["facts"][0]["evidence_chunk_id"] == chunk_id
    assert body["facts"][0]["evidence_quote"] == "knows Bob"

    stmt = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/statements/{statement_id}",
        headers=headers,
    )
    assert stmt.status_code == 200
    assert stmt.json()["statement"]["subject_id"] == alice
    assert stmt.json()["statement"]["statement_id"] == statement_id

    recent = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/entities?limit=10", headers=headers)
    assert recent.status_code == 200
    recent_body = recent.json()
    assert recent_body["total"] >= 2
    recent_ids = {e["id"] for e in recent_body["entities"]}
    assert alice in recent_ids
    assert bob in recent_ids

    page2 = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities?limit=1&offset=1",
        headers=headers,
    )
    assert page2.status_code == 200
    assert page2.json()["total"] >= 2
    assert len(page2.json()["entities"]) == 1
