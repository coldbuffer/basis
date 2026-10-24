"""GraphBuilder ingest must run NER, not treat doc payload as a prebuilt entity."""

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from basis.domain.knowledge.pipeline.document import TextIngestOptions, build_kg_from_text
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.store import KnowledgeStore


def test_build_kg_from_text_runs_llm_ner() -> None:
    kg = build_kg_from_text(
        "english-doc",
        "Alice knows Bob.",
        TextIngestOptions(extract=True, chunk=False),
    )
    names = {
        str(e.get("name") or e.get("id") or "")
        for e in kg.get("entities") or []
        if isinstance(e, dict)
    }
    assert "Alice" in names
    assert "Bob" in names
    assert len(kg.get("relationships") or []) >= 1


def test_version_ingest_writes_entities_to_ledger(tmp_path) -> None:
    from basis.domain.tenancy.admin.store import AdminStore
    from basis.domain.graph.projection.session import GraphSession
    from basis.domain.knowledge.pipeline.version_ingest import run_version_ingest

    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("extract@example.com", "password1", "U")
    workspace = admin.create_workspace(user, "KB", None, "restricted")
    workspace_id = workspace.id
    admin.close()

    blobs = BlobStore(tmp_path)
    knowledge = KnowledgeStore(tmp_path / "basis.db", blobs)
    _, version_id, job_id, _ = knowledge.store_upload_bytes(
        workspace_id,
        title="story.txt",
        mime_type="text/plain",
        data=b"Alice knows Bob.",
        created_by=user.id,
        external_key="story",
    )
    graph = GraphSession()
    result = run_version_ingest(
        knowledge,
        graph,
        workspace_id,
        version_id,
        job_id,
        filename="story.txt",
        graph_doc_id="story",
        options=TextIngestOptions(extract=True, chunk=False),
    )
    assert result["ledger_entities_written"] >= 2
    assert result["ledger_statements_written"] >= 1
    assert graph.stats()["node_count"] >= 3
    knowledge.close()


def test_documents_api_english_extract(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "api@example.com", "password": "password1", "display_name": "U"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    body = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={"doc_id": "en-1", "text": "Alice knows Bob.", "wait": True, "chunk": False},
    ).json()
    assert body.get("ledger_entities_written", 0) >= 2
    stats = client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=headers).json()
    assert stats["node_count"] >= 3
    assert stats["edge_count"] >= 1
