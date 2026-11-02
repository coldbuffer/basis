"""Entity label clustering (F-GOV-04 Phase C)."""

from pathlib import Path

from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.services.governor_cluster import (
    ENTITY_CLUSTER_KIND,
    find_entity_label_clusters,
    scan_entity_label_clusters,
)
from basis.services.knowledge.store import KnowledgeStore


def _workspace_store(tmp_path: Path) -> tuple[str, KnowledgeStore]:
    from basis.services.tenancy.admin.store import AdminStore

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("cl@example.com", "password1", "Cl")
    workspace_id = admin.create_workspace(user, "Cl KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return workspace_id, store


def test_find_clusters_same_label(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    store.create_entity(workspace_id, canonical_label="Alice")
    store.create_entity(workspace_id, canonical_label="alice")
    store.create_entity(workspace_id, canonical_label="Bob")
    clusters = find_entity_label_clusters(store, workspace_id)
    assert len(clusters) == 1
    assert len(clusters[0]["entity_ids"]) == 2


def test_scan_enqueues_cluster_review(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    store.create_entity(workspace_id, canonical_label="Dup")
    store.create_entity(workspace_id, canonical_label="Dup")
    result = scan_entity_label_clusters(store, workspace_id)
    assert result["created"] == 1
    items = store.list_review_items(workspace_id, kind=ENTITY_CLUSTER_KIND)
    assert len(items) == 1


def test_cluster_approve_promotes_entity_merge(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from basis.infra.runtime.config import Settings
    from basis.app import create_app

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ap@example.com", "password": "password1", "display_name": "Ap"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    primary = store.create_entity(workspace_id, canonical_label="Same")
    dup = store.create_entity(workspace_id, canonical_label="same")
    store.close()

    scan_entity_label_clusters(
        KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path)), workspace_id
    )
    items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": ENTITY_CLUSTER_KIND},
    ).json()["items"]
    cluster_id = items[0]["id"]

    approve = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{cluster_id}/approve",
        headers=headers,
        json={"primary_id": dup},
    )
    assert approve.status_code == 200
    merge_items = client.get(
        f"/api/v1/workspaces/{workspace_id}/review/items",
        headers=headers,
        params={"kind": "entity_merge"},
    ).json()["items"]
    assert len(merge_items) == 1
    assert merge_items[0]["payload"]["primary_id"] == dup
    assert primary in merge_items[0]["payload"]["duplicate_ids"]
