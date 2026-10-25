"""Graph decision narratives for review actions."""

from pathlib import Path

from basis.domain.graph.governance.review_decision_record import build_entity_merge_decision
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.tenancy.admin.store import AdminStore


def _store(tmp_path: Path) -> tuple[str, KnowledgeStore]:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("narr@example.com", "password1", "Narr")
    workspace_id = admin.create_workspace(user, "Narr KB", None, "restricted").id
    admin.close()
    knowledge = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return workspace_id, knowledge


def test_build_entity_merge_decision_uses_labels(tmp_path: Path) -> None:
    workspace_id, knowledge = _store(tmp_path)
    primary = knowledge.create_entity(workspace_id, canonical_label="Acme Corp")
    dup = knowledge.create_entity(workspace_id, canonical_label="ACME Corporation")
    scenario, reasoning, detail = build_entity_merge_decision(
        knowledge,
        workspace_id,
        review_item_id="rev-1",
        primary_id=primary,
        duplicate_ids=[dup],
        rationale="Same company",
        merge_result={"edges_updated": 3, "ledger_notice": "graph_only_merge"},
    )
    assert "Acme Corp" in scenario
    assert "ACME Corporation" in reasoning
    assert detail["kind"] == "entity_merge"
    assert detail["primary_label"] == "Acme Corp"
    assert detail["duplicate_labels"][dup] == "ACME Corporation"
    knowledge.close()
