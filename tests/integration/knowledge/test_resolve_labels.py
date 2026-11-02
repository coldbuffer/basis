"""Batch node label resolution for review UI."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.services.tenancy.admin.store import AdminStore
from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.graph.projection.projector import rebuild_graph_from_ledger
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore


def test_resolve_labels_ledger_and_graph(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "lab@example.com", "password": "password1", "display_name": "Lab"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    knowledge: KnowledgeStore = app.state.knowledge_store
    alice = knowledge.create_entity(workspace_id, canonical_label="Alice Ledger")
    session = rebuild_graph_from_ledger(knowledge, workspace_id)
    revision = knowledge.bump_projection_revision(workspace_id)
    app.state.graph_persistence.save(workspace_id, session, projection_revision=revision)

    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/graph/resolve-labels",
        headers=headers,
        json={"ids": [alice, "missing-node"]},
    )
    assert resp.status_code == 200
    labels = resp.json()["labels"]
    assert labels[alice] == "Alice Ledger"
    assert labels["missing-node"] is None
