"""F-GOV-04 governor pass (conflicts + low confidence)."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.services.governor import (
    LOW_CONFIDENCE_KIND,
    run_governor_pass,
    scan_low_confidence_statements,
)
from basis.domain.knowledge.store import KnowledgeStore
from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app


def _workspace_store(tmp_path: Path) -> tuple[str, KnowledgeStore]:
    from basis.domain.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("gov@example.com", "password1", "Gov")
    workspace_id = admin.create_workspace(user, "Gov KB", None, "restricted").id
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
        external_key="gov-doc",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="evidence")
    store.set_version_status(workspace_id, version_id, "ready")
    return chunk_id


def test_scan_low_confidence_enqueues_review(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    chunk_id = _chunk(store, workspace_id)
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    bob = store.create_entity(workspace_id, canonical_label="Bob")
    store.add_open_statement(
        workspace_id,
        subject_id=alice,
        surface_phrase="knows",
        object_entity_id=bob,
        object_value=None,
        status="pending",
        proposed_by="agent",
        chunk_id=chunk_id,
        quote="knows",
        confidence=0.4,
    )
    result = scan_low_confidence_statements(store, workspace_id, confidence_min=0.75)
    assert result["created"] == 1
    items = store.list_review_items(workspace_id, kind=LOW_CONFIDENCE_KIND)
    assert len(items) == 1
    assert items[0]["payload"]["confidence"] == 0.4


def test_governance_ontology_uri_persists(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    uri = "http://example.org/onto/demo"
    updated = store.update_governance_config(
        workspace_id,
        governor_enabled=False,
        governor_interval_minutes=1440,
        governor_confidence_min=0.75,
        governance_ontology_uri=uri,
    )
    assert updated.governance_ontology_uri == uri
    loaded = store.get_governance_config(workspace_id)
    assert loaded.governance_ontology_uri == uri


def test_run_governor_pass_returns_both_sections(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    chunk_id = _chunk(store, workspace_id)
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    bob = store.create_entity(workspace_id, canonical_label="Bob")
    store.add_open_statement(
        workspace_id,
        subject_id=alice,
        surface_phrase="knows",
        object_entity_id=bob,
        object_value=None,
        status="pending",
        proposed_by="agent",
        chunk_id=chunk_id,
        quote="knows",
        confidence=0.3,
    )
    body = run_governor_pass(store, workspace_id, confidence_min=0.75)
    assert body["confidence_min"] == 0.75
    assert body["low_confidence"]["created"] == 1
    assert "shacl_scan" in body


def test_governor_run_http_and_approve_low_confidence(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "api@example.com", "password": "password1", "display_name": "API"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    chunk_id = _chunk(store, workspace_id)
    a = store.create_entity(workspace_id, canonical_label="X")
    b = store.create_entity(workspace_id, canonical_label="Y")
    low_sid = store.add_open_statement(
        workspace_id,
        subject_id=a,
        surface_phrase="relates",
        object_entity_id=b,
        object_value=None,
        status="pending",
        proposed_by="agent",
        chunk_id=chunk_id,
        quote="relates",
        confidence=0.2,
    )
    store.close()

    run = client.post(
        f"/api/v1/workspaces/{workspace_id}/governance/governor/run",
        headers=headers,
        json={"confidence_min": 0.75},
    )
    assert run.status_code == 200

    empty_scope = client.post(
        f"/api/v1/workspaces/{workspace_id}/governance/governor/run",
        headers=headers,
        json={
            "include_shacl": False,
            "include_low_confidence": False,
            "include_entity_label_clusters": False,
            "include_unmapped_entity_types": False,
            "include_graph_dedup": False,
        },
    )
    assert empty_scope.status_code == 422
    assert empty_scope.json()["detail"]["code"] == "governor_scan_empty"

    shacl_only = client.post(
        f"/api/v1/workspaces/{workspace_id}/governance/governor/run",
        headers=headers,
        json={
            "include_shacl": True,
            "include_low_confidence": False,
            "include_entity_label_clusters": False,
            "include_graph_dedup": False,
        },
    )
    assert shacl_only.status_code == 200
    assert shacl_only.json()["low_confidence"]["created"] == 0
    assert run.json()["low_confidence"]["created"] == 1

    items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": LOW_CONFIDENCE_KIND},
    ).json()["items"]
    item_id = items[0]["id"]

    approve = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{item_id}/approve",
        headers=headers,
        json={"rationale": "ok"},
    )
    assert approve.status_code == 200

    store2 = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    row = store2.get_statement_browse(workspace_id, statement_id=low_sid)
    assert row is not None
    assert row["status"] == "confirmed"
    store2.close()
