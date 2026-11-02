"""Document timeline API (F-TIM-02)."""

from pathlib import Path

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from basis.services.tenancy.admin.store import AdminStore
from basis.app import create_app


def test_list_document_timeline_events_unit(tmp_path: Path) -> None:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("tl@example.com", "password1", "U")
    workspace_id = admin.create_workspace(user, "KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    doc_uuid, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="a.txt",
        mime_type="text/plain",
        data=b"hello",
        created_by=None,
        external_key="doc-tl",
    )
    store.set_version_status(workspace_id, version_id, "ready")
    events = store.list_document_timeline_events(workspace_id, doc_uuid)
    kinds = {e["kind"] for e in events}
    assert "version_created" in kinds
    store.close()


def test_document_timeline_route_after_ingest(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "tl2@example.com", "password": "password1", "display_name": "TL"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}

    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "tl2", "text": "Kim knows Lou.", "wait": True, "extract": True},
    ).json()

    doc_ref = created.get("document_id") or created.get("doc_id") or "tl2"
    timeline = client.get(
        f"/api/v1/workspaces/{workspace_id}/documents/{doc_ref}/timeline",
        headers=headers,
    )
    assert timeline.status_code == 200
    body = timeline.json()
    assert body.get("document_id")
    kinds = {e["kind"] for e in body.get("events") or []}
    assert "version_created" in kinds
