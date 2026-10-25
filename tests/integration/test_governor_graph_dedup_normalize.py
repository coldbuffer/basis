"""Governor graph dedup pair normalization (Semantica DuplicateCandidate)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.services.governor_graph_dedup import (
    _normalize_dedup_pair,
    scan_graph_semantic_dedup_clusters,
)
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.tenancy.admin.store import AdminStore


def _workspace_store(tmp_path: Path) -> tuple[str, KnowledgeStore]:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("dedup@example.com", "password1", "Dedup")
    workspace_id = admin.create_workspace(user, "Dedup KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return workspace_id, store


def test_normalize_dedup_pair_accepts_duplicate_candidate() -> None:
    class _Candidate:
        entity1 = {"id": "a", "text": "Foo"}
        entity2 = {"id": "b", "text": "Foo Bar"}
        similarity_score = 0.55

    pair = _normalize_dedup_pair(_Candidate())
    assert pair is not None
    assert pair["entity1"]["id"] == "a"
    assert pair["similarity"] == 0.55


def test_scan_graph_dedup_enqueues_duplicate_candidate_objects(tmp_path: Path) -> None:
    import asyncio

    workspace_id, store = _workspace_store(tmp_path)

    class _Candidate:
        entity1 = {"id": "node-a", "text": "Acme Corp"}
        entity2 = {"id": "node-b", "text": "Acme Corporation"}
        similarity_score = 0.52

    with patch(
        "basis.domain.knowledge.services.governor_graph_dedup._detect_duplicate_pairs",
        new_callable=AsyncMock,
        return_value=[_Candidate()],
    ):
        result = asyncio.run(
            scan_graph_semantic_dedup_clusters(
                store,
                workspace_id,
                session=object(),
                threshold=0.5,
            )
        )
    assert result["created"] == 1
    items = store.list_review_items(workspace_id, status="open", kind="entity_cluster", limit=10)
    assert items[0]["payload"]["source"] == "graph_semantic_dedup"
    assert items[0]["payload"]["similarity"] == 0.52
    store.close()
