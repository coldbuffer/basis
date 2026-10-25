"""SHACL conflict detection → review queue (F-RUL-04)."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.conflict.policy import resolve_predicate_policy
from basis.domain.knowledge.conflict.shacl_scan import (
    SHACL_VIOLATION_KIND,
    find_shacl_violation_payloads,
)
from basis.domain.knowledge.services.conflict_review import run_shacl_conflict_scan
from basis.domain.knowledge.store import KnowledgeStore


def _workspace_store(tmp_path: Path) -> tuple[str, KnowledgeStore]:
    from basis.domain.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("conf@example.com", "password1", "Conf")
    workspace_id = admin.create_workspace(user, "Conf KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return workspace_id, store


def _chunk(store: KnowledgeStore, workspace_id: str) -> str:
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="t.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="conf-doc",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="evidence")
    store.set_version_status(workspace_id, version_id, "ready")
    return chunk_id


def test_contains_allows_multiple_objects(tmp_path: Path) -> None:
    policy = resolve_predicate_policy("CONTAINS", {})
    assert policy["allows_multiple_objects"] is True


def test_scan_enqueues_shacl_when_mapped(tmp_path: Path) -> None:
    from basis.domain.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("map@example.com", "password1", "Map")
    admin.close()
    workspace_id, store = _workspace_store(tmp_path)
    store.create_mapping(
        workspace_id,
        actor_id=user.id,
        signature="employed_by",
        target_uri="http://example.org/employer",
        target_kind="property",
        direction="forward",
        status="confirmed",
    )
    chunk_id = _chunk(store, workspace_id)
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    bob = store.create_entity(workspace_id, canonical_label="Bob")
    carol = store.create_entity(workspace_id, canonical_label="Carol")
    for obj in (bob, carol):
        store.add_open_statement(
            workspace_id,
            subject_id=alice,
            surface_phrase="employed_by",
            object_entity_id=obj,
            object_value=None,
            status="confirmed",
            proposed_by="test",
            chunk_id=chunk_id,
            quote="employed_by",
        )
    out = run_shacl_conflict_scan(store, workspace_id)
    assert out["created"] >= 1
    assert len(store.list_review_items(workspace_id, kind=SHACL_VIOLATION_KIND)) >= 1


def test_shacl_scan_enqueues_item(tmp_path: Path) -> None:
    from basis.domain.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("only@example.com", "password1", "Only")
    admin.close()
    workspace_id, store = _workspace_store(tmp_path)
    store.create_mapping(
        workspace_id,
        actor_id=user.id,
        signature="title",
        target_uri="http://example.org/title",
        target_kind="property",
        direction="forward",
        status="confirmed",
    )
    chunk_id = _chunk(store, workspace_id)
    person = store.create_entity(workspace_id, canonical_label="Person")
    for value in ("CEO", "Founder"):
        store.add_open_statement(
            workspace_id,
            subject_id=person,
            surface_phrase="title",
            object_entity_id=None,
            object_value=value,
            status="confirmed",
            proposed_by="test",
            chunk_id=chunk_id,
            quote=value,
        )
    out = run_shacl_conflict_scan(store, workspace_id)
    assert out["created"] >= 1
    assert len(store.list_review_items(workspace_id, kind=SHACL_VIOLATION_KIND)) >= 1


def test_shacl_detects_mapped_max_count_violation(tmp_path: Path) -> None:
    from basis.domain.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("shacl@example.com", "password1", "Shacl")
    admin.close()
    workspace_id, store = _workspace_store(tmp_path)
    store.create_mapping(
        workspace_id,
        actor_id=user.id,
        signature="title",
        target_uri="http://example.org/title",
        target_kind="property",
        direction="forward",
        status="confirmed",
    )
    chunk_id = _chunk(store, workspace_id)
    person = store.create_entity(workspace_id, canonical_label="Person")
    for value in ("CEO", "Founder"):
        store.add_open_statement(
            workspace_id,
            subject_id=person,
            surface_phrase="title",
            object_entity_id=None,
            object_value=value,
            status="confirmed",
            proposed_by="test",
            chunk_id=chunk_id,
            quote=value,
        )
    payloads = find_shacl_violation_payloads(store, workspace_id)
    assert any(p.get("rule_id") == "shacl:constraint" for p in payloads)


def test_scan_materializes_confirmed_mappings(tmp_path: Path) -> None:
    from basis.domain.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("mat@example.com", "password1", "Mat")
    admin.close()
    workspace_id, store = _workspace_store(tmp_path)
    mapping = store.create_mapping(
        workspace_id,
        actor_id=user.id,
        signature="role",
        target_uri="http://example.org/role",
        target_kind="property",
        direction="forward",
        status="confirmed",
    )
    chunk_id = _chunk(store, workspace_id)
    person = store.create_entity(workspace_id, canonical_label="Person")
    store.add_open_statement(
        workspace_id,
        subject_id=person,
        surface_phrase="role",
        object_entity_id=None,
        object_value="admin",
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="admin",
    )
    out = run_shacl_conflict_scan(store, workspace_id)
    assert out.get("materialize", {}).get("facts_created", 0) >= 1
    facts = store.list_typed_facts(workspace_id, limit=20)
    assert any(f.get("mapping_id") == mapping["id"] for f in facts)


def test_run_shacl_conflict_scan_route(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "scan@example.com", "password": "password1", "display_name": "Scan"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    store.create_mapping(
        workspace_id,
        actor_id=admin["user"]["id"],
        signature="works_with",
        target_uri="http://example.org/worksWith",
        target_kind="property",
        direction="forward",
        status="confirmed",
    )
    chunk_id = _chunk(store, workspace_id)
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    bob = store.create_entity(workspace_id, canonical_label="Bob")
    carol = store.create_entity(workspace_id, canonical_label="Carol")
    for obj in (bob, carol):
        store.add_open_statement(
            workspace_id,
            subject_id=alice,
            surface_phrase="works_with",
            object_entity_id=obj,
            object_value=None,
            status="confirmed",
            proposed_by="test",
            chunk_id=chunk_id,
            quote="works_with",
        )
    res = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/scan-shacl-violations",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json().get("created", 0) >= 1


def test_acknowledge_shacl_review_item(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rc@example.com", "password": "password1", "display_name": "RC"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    store.create_mapping(
        workspace_id,
        actor_id=admin["user"]["id"],
        signature="title",
        target_uri="http://example.org/title",
        target_kind="property",
        direction="forward",
        status="confirmed",
    )
    chunk_id = _chunk(store, workspace_id)
    person = store.create_entity(workspace_id, canonical_label="Person")
    for value in ("A", "B"):
        store.add_open_statement(
            workspace_id,
            subject_id=person,
            surface_phrase="title",
            object_entity_id=None,
            object_value=value,
            status="confirmed",
            proposed_by="test",
            chunk_id=chunk_id,
            quote=value,
        )
    run_shacl_conflict_scan(store, workspace_id)
    item_id = store.list_review_items(workspace_id, kind=SHACL_VIOLATION_KIND)[0]["id"]

    approved = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{item_id}/approve",
        headers=headers,
        json={"rationale": "reviewed"},
    )
    assert approved.status_code == 200
    assert approved.json()["item"]["status"] == "approved"
