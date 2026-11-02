"""Delete a ledger entity after previewing the statements that go with it."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore


def _seed(tmp_path: Path) -> tuple[TestClient, dict[str, str], str, KnowledgeStore]:
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "del@example.com", "password": "password1", "display_name": "Del"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return client, headers, workspace_id, store


def test_delete_entity_removes_subject_and_object_statements(tmp_path: Path) -> None:
    client, headers, workspace_id, store = _seed(tmp_path)
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="d.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="d1",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="Alice knows Bob. Carol sees Bob.")
    store.set_version_status(workspace_id, version_id, "ready")
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    bob = store.create_entity(workspace_id, canonical_label="Bob")
    carol = store.create_entity(workspace_id, canonical_label="Carol")
    lonely = store.create_entity(workspace_id, canonical_label="Lonely")
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
    store.add_open_statement(
        workspace_id,
        subject_id=carol,
        surface_phrase="sees",
        object_entity_id=bob,
        object_value=None,
        status="pending",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="sees Bob",
    )
    derived_id = store.insert_derived_fact(
        workspace_id,
        subject_id=alice,
        predicate_uri="urn:basis:pred:knows",
        object_entity_id=bob,
        object_value=None,
        rule_id=None,
        derivations=[],
    )
    store.close()
    assert derived_id

    preview = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{alice}/delete-preview",
        headers=headers,
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["statement_count"] == 1
    assert body["statements"][0]["surface_phrase"] == "knows"
    assert body["statements"][0]["object_label"] == "Bob"
    assert body["statements"][0]["evidence_quote"] == "knows Bob"
    assert body["derived_fact_count"] == 1

    lonely_preview = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{lonely}/delete-preview",
        headers=headers,
    )
    assert lonely_preview.status_code == 200
    assert lonely_preview.json()["statement_count"] == 0
    assert lonely_preview.json()["statements"] == []

    deleted = client.delete(f"/api/v1/workspaces/{workspace_id}/ledger/entities/{alice}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["statements_removed"] == 1
    assert deleted.json()["derived_facts_removed"] == 1

    remaining = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/entities?query=Alice", headers=headers)
    assert remaining.json()["entities"] == []
    bob_facts = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{bob}/facts",
        headers=headers,
    )
    assert bob_facts.status_code == 200
    assert bob_facts.json()["facts"] == []

    bob_preview = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{bob}/delete-preview",
        headers=headers,
    )
    assert bob_preview.status_code == 200
    bob_body = bob_preview.json()
    assert bob_body["statement_count"] == 1
    assert bob_body["statements"][0]["role"] == "object"
    assert bob_body["statements"][0]["subject_label"] == "Carol"
    assert bob_body["statements"][0]["surface_phrase"] == "sees"

    removed_bob = client.delete(f"/api/v1/workspaces/{workspace_id}/ledger/entities/{bob}", headers=headers)
    assert removed_bob.status_code == 200
    assert removed_bob.json()["statements_removed"] == 1
    carol_left = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/entities?query=Carol", headers=headers)
    assert [row["id"] for row in carol_left.json()["entities"]] == [carol]

    removed_lonely = client.delete(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{lonely}",
        headers=headers,
    )
    assert removed_lonely.status_code == 200
    assert removed_lonely.json()["statements_removed"] == 0


def test_viewer_cannot_delete_entity(tmp_path: Path) -> None:
    client, owner_headers, workspace_id, store = _seed(tmp_path)
    lonely = store.create_entity(workspace_id, canonical_label="Keep")
    store.close()

    viewer = client.post(
        "/api/v1/auth/register",
        json={"email": "view@example.com", "password": "password1", "display_name": "View"},
    ).json()
    users = client.get("/api/v1/users", headers=owner_headers).json()["users"]
    viewer_id = next(user["id"] for user in users if user["email"] == "view@example.com")
    added = client.put(
        f"/api/v1/workspaces/{workspace_id}/members/{viewer_id}",
        headers=owner_headers,
        json={"role": "viewer"},
    )
    assert added.status_code == 200
    viewer_headers = {"Authorization": f"Bearer {viewer['token']}"}

    preview = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{lonely}/delete-preview",
        headers=viewer_headers,
    )
    assert preview.status_code == 403
    deleted = client.delete(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{lonely}",
        headers=viewer_headers,
    )
    assert deleted.status_code == 403
