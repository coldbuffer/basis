"""Graph decision narratives for review actions."""

from pathlib import Path

from basis.services.graph.governance.decision import record_governance_decision_for_workspace
from basis.services.graph.governance.review_decision_record import build_entity_merge_decision
from basis.services.graph.projection.session import GraphSession
from basis.services.graph.session.registry import GraphRuntime
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore
from basis.services.tenancy.admin.store import AdminStore


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


def test_record_merge_decision_links_entity_ids() -> None:
    session = GraphSession()
    session.graph.add_node("entity-a", "entity", content="Alice")
    session.graph.add_node("entity-b", "entity", content="Bob")
    runtime = GraphRuntime(
        workspace_id="ws",
        projection_revision=0,
        basis=session,
        adapter=session,
    )
    persisted: list[str] = []
    decision_id = record_governance_decision_for_workspace(
        "ws",
        message="实体合并：保留 Alice",
        detail={
            "kind": "entity_merge",
            "review_item_id": "rev-1",
            "primary_id": "entity-a",
            "duplicate_ids": ["entity-b", "entity-gone"],
            "duplicate_labels": {"entity-b": "Bob"},
        },
        actor_id="user-1",
        category="merge",
        outcome="approved",
        reasoning="同一实体",
        runtime_loader=lambda: runtime,
        persist_graph=persisted.append,
    )
    assert decision_id
    assert persisted == ["ws"]
    neighbor_ids = {row["id"] for row in session.graph.get_neighbors(decision_id, hops=1)}
    assert "entity-a" in neighbor_ids
    assert "entity-b" in neighbor_ids
    assert "entity-gone" not in session.graph.nodes
    kept = session.graph.nodes["entity-a"]
    assert kept.node_type == "entity"
    assert kept.content == "Alice"
