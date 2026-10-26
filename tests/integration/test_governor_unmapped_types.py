"""Governor scan for taxonomic labels without confirmed class mappings."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.domain.graph.projection.snapshot_store import GraphPersistence
from basis.domain.knowledge.blob_store import BlobStore
from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app
from tests.integration.ontology_hub_sidecar import write_alignment_sidecar
from basis.domain.knowledge.services.governor_unmapped_types import (
    UNMAPPED_ENTITY_TYPE_KIND,
    scan_unmapped_entity_type_labels,
)
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.tenancy.admin.store import AdminStore


def _workspace_store(tmp_path: Path) -> tuple[str, KnowledgeStore, str]:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("unmap@example.com", "password1", "Unmap")
    workspace_id = admin.create_workspace(user, "Unmap KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return workspace_id, store, user.id


def _chunk(store: KnowledgeStore, workspace_id: str) -> str:
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="t.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="unmap-doc",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="evidence")
    store.set_version_status(workspace_id, version_id, "ready")
    return chunk_id


def test_scan_unmapped_includes_vocabulary_alignment_hints(tmp_path: Path) -> None:
    workspace_id, store, _user_id = _workspace_store(tmp_path)
    chunk_id = _chunk(store, workspace_id)
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    store.add_open_statement(
        workspace_id,
        subject_id=alice,
        surface_phrase="是",
        object_entity_id=None,
        object_value="人",
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="是人",
    )
    align_store = {
        "a1": {
            "id": "a1",
            "source_uri": "http://example.org/a#Person",
            "target_uri": "https://schema.org/Person",
            "source_label": "人",
            "target_label": "Person",
            "relation": "skos:exactMatch",
            "confidence": 0.9,
        }
    }
    scan_unmapped_entity_type_labels(store, workspace_id, align_store=align_store)
    items = store.list_review_items(workspace_id, kind=UNMAPPED_ENTITY_TYPE_KIND)
    hints = items[0]["payload"].get("vocabulary_alignment_suggestions") or []
    assert any(row.get("uri") == "http://example.org/a#Person" for row in hints)


def test_scan_unmapped_entity_type_labels_enqueues_review(tmp_path: Path) -> None:
    workspace_id, store, user_id = _workspace_store(tmp_path)
    chunk_id = _chunk(store, workspace_id)
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    store.add_open_statement(
        workspace_id,
        subject_id=alice,
        surface_phrase="是",
        object_entity_id=None,
        object_value="人",
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="是人",
    )

    result = scan_unmapped_entity_type_labels(store, workspace_id)
    assert result["created"] == 1
    items = store.list_review_items(workspace_id, kind=UNMAPPED_ENTITY_TYPE_KIND)
    assert len(items) == 1
    assert items[0]["payload"]["label"] == "人"

    store.create_mapping(
        workspace_id,
        actor_id=user_id,
        signature="人",
        target_uri="http://example.org/Person",
        target_kind="class",
        direction="n/a",
        status="confirmed",
    )
    again = scan_unmapped_entity_type_labels(store, workspace_id)
    assert again["created"] == 0
    assert again["skipped"] == 0


def test_confirmed_class_mapping_resolves_unmapped_review(tmp_path: Path) -> None:
    from basis.domain.knowledge.services.governor_unmapped_types import (
        maybe_resolve_unmapped_entity_type_for_mapping,
    )

    workspace_id, store, user_id = _workspace_store(tmp_path)
    chunk_id = _chunk(store, workspace_id)
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    store.add_open_statement(
        workspace_id,
        subject_id=alice,
        surface_phrase="是",
        object_entity_id=None,
        object_value="犬",
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="是犬",
    )
    scan_unmapped_entity_type_labels(store, workspace_id)
    assert len(store.list_review_items(workspace_id, kind=UNMAPPED_ENTITY_TYPE_KIND)) == 1

    mapping = store.create_mapping(
        workspace_id,
        actor_id=user_id,
        signature="犬",
        target_uri="http://example.org/Dog",
        target_kind="class",
        direction="n/a",
        status="proposed",
    )
    confirmed = store.update_mapping_status(workspace_id, mapping["id"], user_id, status="confirmed")
    maybe_resolve_unmapped_entity_type_for_mapping(
        store,
        workspace_id,
        confirmed,
        resolved_by=user_id,
    )

    open_items = store.list_review_items(workspace_id, kind=UNMAPPED_ENTITY_TYPE_KIND, status="open")
    assert open_items == []


def test_http_confirm_class_mapping_closes_unmapped_review(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "unmaphttp@example.com", "password": "password1", "display_name": "Unmap HTTP"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    chunk_id = _chunk(store, workspace_id)
    subject = store.create_entity(workspace_id, canonical_label="Bob")
    store.add_open_statement(
        workspace_id,
        subject_id=subject,
        surface_phrase="是",
        object_entity_id=None,
        object_value="猫",
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="是猫",
    )
    store.close()

    governor = client.post(
        f"/api/v1/workspaces/{workspace_id}/governance/governor/run",
        headers=headers,
        json={
            "include_shacl": False,
            "include_low_confidence": False,
            "include_entity_label_clusters": False,
            "include_graph_dedup": False,
            "include_unmapped_entity_types": True,
        },
    )
    assert governor.status_code == 200
    assert governor.json()["unmapped_entity_types"]["created"] == 1

    items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": UNMAPPED_ENTITY_TYPE_KIND},
    ).json()["items"]
    assert len(items) == 1
    assert items[0]["payload"]["label"] == "猫"

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/mappings",
        headers=headers,
        json={
            "signature": "猫",
            "target_uri": "http://example.org/Cat",
            "target_kind": "class",
            "direction": "n/a",
            "status": "proposed",
        },
    )
    assert created.status_code == 200
    mapping_id = created.json()["mapping"]["id"]

    confirmed = client.post(
        f"/api/v1/workspaces/{workspace_id}/mappings/{mapping_id}/status",
        headers=headers,
        json={"status": "confirmed"},
    )
    assert confirmed.status_code == 200

    open_items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": UNMAPPED_ENTITY_TYPE_KIND, "status": "open"},
    ).json()["items"]
    assert open_items == []


def test_http_governor_unmapped_includes_l1_hints_from_sidecar(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "unmapl1@example.com", "password": "password1", "display_name": "Unmap L1"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    chunk_id = _chunk(store, workspace_id)
    subject = store.create_entity(workspace_id, canonical_label="Carol")
    store.add_open_statement(
        workspace_id,
        subject_id=subject,
        surface_phrase="是",
        object_entity_id=None,
        object_value="鱼",
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="是鱼",
    )
    store.close()

    persistence = GraphPersistence(tmp_path)
    write_alignment_sidecar(
        persistence,
        workspace_id,
        {
            "a1": {
                "id": "a1",
                "source_uri": "http://example.org/a#Fish",
                "target_uri": "https://schema.org/Fish",
                "source_label": "鱼",
                "target_label": "Fish",
                "relation": "skos:exactMatch",
                "confidence": 0.9,
            }
        },
    )

    governor = client.post(
        f"/api/v1/workspaces/{workspace_id}/governance/governor/run",
        headers=headers,
        json={
            "include_shacl": False,
            "include_low_confidence": False,
            "include_entity_label_clusters": False,
            "include_graph_dedup": False,
            "include_unmapped_entity_types": True,
        },
    )
    assert governor.status_code == 200

    items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": UNMAPPED_ENTITY_TYPE_KIND},
    ).json()["items"]
    assert len(items) == 1
    hints = items[0]["payload"].get("vocabulary_alignment_suggestions") or []
    assert any(row.get("uri") == "http://example.org/a#Fish" for row in hints)
