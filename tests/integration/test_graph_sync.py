"""Graph-only nodes and edges are written into the ledger before a snapshot save."""

from pathlib import Path

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from basis.domain.graph.projection.projector import apply_rebuild_to_session
from basis.domain.graph.projection.session import GraphSession
from basis.domain.knowledge.services.graph_sync import sync_graph_to_ledger
from basis.domain.knowledge.store import KnowledgeStore


def test_sync_graph_to_ledger_keeps_imported_edge_across_rebuild(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "sync@example.com", "password": "password1", "display_name": "Sync"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    knowledge: KnowledgeStore = client.app.state.knowledge_store

    session = GraphSession()
    session.add_node("n-alice", "entity", content="Imported Alice")
    session.add_node("n-bob", "entity", content="Imported Bob")
    session.add_node("cls-person", "owl:Class", content="Person")
    session.add_node("doc-1", "document", content="A document")
    session.add_edge("n-alice", "n-bob", "knows")
    session.add_edge("n-alice", "doc-1", "mentioned_in")

    first = sync_graph_to_ledger(knowledge, workspace_id, session)
    assert first["entities_created"] == 0
    assert first["statements_created"] == 1

    again = sync_graph_to_ledger(knowledge, workspace_id, session)
    assert again["statements_created"] == 0

    labels = {
        row["canonical_label"]
        for row in client.get(f"/api/v1/workspaces/{workspace_id}/ledger/entities?limit=20", headers=headers).json()[
            "entities"
        ]
    }
    assert "Imported Alice" in labels
    assert "Imported Bob" in labels
    assert "Person" not in labels

    apply_rebuild_to_session(knowledge, workspace_id, session)
    rebuilt_labels = {
        (node.content or "")
        for node in session.graph.nodes.values()
        if node.node_type == "entity"
    }
    assert "Imported Alice" in rebuilt_labels
    assert "Imported Bob" in rebuilt_labels
    edges = session.graph.edges
    edge_values = edges.values() if isinstance(edges, dict) else edges
    assert any(edge.edge_type == "knows" for edge in edge_values)

    third = sync_graph_to_ledger(knowledge, workspace_id, session)
    assert third == {"entities_created": 0, "statements_created": 0}


def test_sync_graph_mcp_slug_id_uses_display_label_once(tmp_path: Path) -> None:
    """MCP add_entity uses slug id + display content; ledger must not duplicate both."""
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "mcp-sync@example.com", "password": "password1", "display_name": "MCP"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    knowledge: KnowledgeStore = client.app.state.knowledge_store

    display = "Trellis（mindfold-ai/Trellis Spec-Driven AI 编码工程框架）"
    session = GraphSession()
    session.add_node("trellis", "Framework", content=display)
    session.add_node("doc-trellis-guide", "Document", content="Trellis 工程化实践指南")
    session.add_edge("trellis", "doc-trellis-guide", "DOCUMENTS")

    # Pre-seed mistaken slug-keyed entity (regression for duplicate ledger rows).
    knowledge.get_or_create_entity_by_label(workspace_id, "trellis")

    sync_graph_to_ledger(knowledge, workspace_id, session)
    apply_rebuild_to_session(knowledge, workspace_id, session)
    session.add_node("trellis", "Framework", content=display)
    session.add_node("doc-trellis-guide", "Document", content="Trellis 工程化实践指南")
    session.add_edge("trellis", "doc-trellis-guide", "DOCUMENTS")
    sync_graph_to_ledger(knowledge, workspace_id, session)

    entities = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities?limit=50",
        headers=headers,
    ).json()["entities"]
    redirect = knowledge.entity_merge_redirect(workspace_id)
    active = [row for row in entities if row["id"] not in redirect]
    labels = {row["canonical_label"] for row in active}
    assert display in labels
    assert "trellis" not in labels
    assert "Trellis 工程化实践指南" in labels
    assert len(active) == 2
