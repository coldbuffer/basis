"""Chunk search HTTP limit cap."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore
from basis.infra.runtime.limits import CHUNK_SEARCH_MAX_LIMIT


def test_chunk_search_route_caps_limit(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "cap@example.com", "password": "password1", "display_name": "Cap"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="one.txt",
        mime_type="text/plain",
        data=b"alpha beta gamma",
        created_by=None,
        external_key="one",
    )
    store.create_chunk(workspace_id, version_id, ordinal=0, text="alpha beta gamma delta")
    store.set_version_status(workspace_id, version_id, "ready")
    store.close()

    res = client.get(
        f"/api/v1/workspaces/{workspace_id}/search?q=alpha&limit=999",
        headers=headers,
    )
    assert res.status_code == 200
    chunks = res.json()["chunks"]
    assert len(chunks) <= CHUNK_SEARCH_MAX_LIMIT

    scoped = client.get(
        f"/api/v1/workspaces/{workspace_id}/search?q=alpha&document_id=one",
        headers=headers,
    )
    assert scoped.status_code == 200
    assert len(scoped.json()["chunks"]) >= 1
