from pathlib import Path

from basis.domain.tenancy.admin.store import AdminStore
from basis.domain.graph.reads.diff import diff_graph_states
from basis.domain.graph.projection.projector import (
    build_temporal_graph_from_ledger,
    graph_projection_signature,
    rebuild_graph_from_ledger,
)
from basis.domain.graph.projection.session import GraphSession
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.knowledge.pipeline.ledger_extract import apply_kg_to_ledger
from basis.domain.knowledge.services.derived_facts_service import persist_reasoning_derived


def _workspace_store(tmp_path: Path) -> tuple[str, KnowledgeStore]:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("proj@example.com", "password1", "U")
    workspace_id = admin.create_workspace(user, "KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return workspace_id, store


def test_rebuild_is_idempotent_and_uses_entity_uuids(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="doc.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="doc-a",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="Alice knows Bob.")
    store.set_version_status(workspace_id, version_id, "ready")
    e1 = store.create_entity(workspace_id, canonical_label="Alice")
    e2 = store.create_entity(workspace_id, canonical_label="Alice")
    assert e1 != e2
    kg = {
        "entities": [{"name": "Alice"}, {"name": "Bob"}],
        "relationships": [{"source": "Alice", "target": "Bob", "predicate": "knows"}],
    }
    apply_kg_to_ledger(
        store, workspace_id, version_id, chunk_id, "Alice knows Bob.", kg, proposed_by="test"
    )

    first = rebuild_graph_from_ledger(store, workspace_id)
    second = rebuild_graph_from_ledger(store, workspace_id)
    assert graph_projection_signature(first) == graph_projection_signature(second)
    assert e1 in first.graph.nodes
    assert e2 in first.graph.nodes
    state = store.get_projection_state(workspace_id)
    assert state["status"] == "clean"
    assert state["revision"] >= 2
    store.close()


def test_invalidated_statement_omitted_from_projection(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="t.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="doc-b",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="A relates B.")
    store.set_version_status(workspace_id, version_id, "ready")
    a = store.create_entity(workspace_id, canonical_label="A")
    b = store.create_entity(workspace_id, canonical_label="B")
    sid = store.add_open_statement(
        workspace_id,
        subject_id=a,
        surface_phrase="relates",
        object_entity_id=b,
        object_value=None,
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="relates",
    )
    with_edge = rebuild_graph_from_ledger(store, workspace_id)
    assert any(
        edge[2] == "relates" for edge in graph_projection_signature(with_edge)["edges"]
    )
    store.invalidate_statement(workspace_id, sid)
    without = rebuild_graph_from_ledger(store, workspace_id)
    assert not any(edge[2] == "relates" for edge in graph_projection_signature(without)["edges"])
    store.close()


def test_derived_facts_projected_as_edges(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    subj = store.get_or_create_entity_by_label(workspace_id, "DerSubj")
    obj = store.get_or_create_entity_by_label(workspace_id, "DerObj")
    persist_reasoning_derived(
        store,
        workspace_id,
        [
            {
                "conclusion": "knows(DerSubj, DerObj)",
                "rule": "IF parent(DerSubj, DerObj) THEN knows(DerSubj, DerObj)",
                "premises": ["parent(DerSubj, DerObj)"],
            }
        ],
    )
    session = rebuild_graph_from_ledger(store, workspace_id)
    sig = graph_projection_signature(session)
    assert any(
        src == subj and tgt == obj and label == "knows"
        for src, tgt, label in sig["edges"]
    )
    store.close()


def test_projection_valid_from_enables_temporal_node_diff(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="t.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="doc-temporal",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="Early knows Late.")
    store.set_version_status(workspace_id, version_id, "ready")
    early = store.create_entity(workspace_id, canonical_label="EarlyEnt")
    late = store.create_entity(workspace_id, canonical_label="LateEnt")
    sid = store.add_open_statement(
        workspace_id,
        subject_id=early,
        surface_phrase="knows",
        object_entity_id=late,
        object_value=None,
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="knows",
    )
    with store._lock:
        store._conn.execute(
            "UPDATE statements SET recorded_at = ? WHERE id = ?",
            ("2020-06-01T00:00:00", sid),
        )
        store._conn.commit()

    session = rebuild_graph_from_ledger(store, workspace_id)
    before = session.graph.state_at("2020-01-01T00:00:00")
    after = session.graph.state_at("2021-01-01T00:00:00")
    before_ids = {n["id"] for n in before["nodes"]}
    assert early not in before_ids
    assert late not in before_ids
    diff = diff_graph_states(before, after)
    assert late in diff["added_nodes"]
    assert early in diff["added_nodes"]
    after_nodes = {n["id"]: n for n in after["nodes"]}
    assert after_nodes[early].get("valid_from") or (
        after_nodes[early].get("properties") or {}
    ).get("valid_from")
    store.close()


def test_temporal_projection_lists_invalidated_statements(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="inv.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="doc-inv",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="A knows B.")
    store.set_version_status(workspace_id, version_id, "ready")
    subj = store.create_entity(workspace_id, canonical_label="EntA")
    obj = store.create_entity(workspace_id, canonical_label="EntB")
    sid = store.add_open_statement(
        workspace_id,
        subject_id=subj,
        surface_phrase="knows",
        object_entity_id=obj,
        object_value=None,
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="knows",
    )
    store.invalidate_statement(workspace_id, sid)
    rows = store.list_statements_for_temporal_projection(workspace_id)
    match = next(r for r in rows if r["statement_id"] == sid)
    assert match["status"] == "invalidated"
    assert match.get("invalidated_at")
    store.close()


def test_ontology_node_preserved_on_rebuild(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    existing = GraphSession()
    existing.add_node(
        "http://example.org/onto#ontology",
        "owl:Ontology",
        content="Demo",
        namespace="http://example.org/onto",
    )
    rebuilt = rebuild_graph_from_ledger(store, workspace_id, preserve_from=existing)
    assert "http://example.org/onto#ontology" in rebuilt.graph.nodes
    store.close()


def test_schema_subgraph_preserved_on_rebuild(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    existing = GraphSession()
    existing.add_node("http://example.org/onto#A", "owl:Class", content="ClassA")
    existing.add_node("http://example.org/onto#B", "owl:Class", content="ClassB")
    existing.add_edge(
        "http://example.org/onto#B",
        "http://example.org/onto#A",
        "rdfs:subClassOf",
    )
    rebuilt = rebuild_graph_from_ledger(store, workspace_id, preserve_from=existing)
    assert "http://example.org/onto#A" in rebuilt.graph.nodes
    assert "http://example.org/onto#B" in rebuilt.graph.nodes
    edges = rebuilt.graph.edges
    edge_values = edges.values() if isinstance(edges, dict) else edges
    assert any(
        edge.source_id == "http://example.org/onto#B"
        and edge.target_id == "http://example.org/onto#A"
        and edge.edge_type == "rdfs:subClassOf"
        for edge in edge_values
    )
    store.close()


def test_temporal_graph_projection_valid_until_filters_invalidated_edges_and_nodes(
    tmp_path: Path,
) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="valid_until.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="doc-valid-until",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="Alpha partners Beta.")
    store.set_version_status(workspace_id, version_id, "ready")
    alpha = store.create_entity(workspace_id, canonical_label="Alpha")
    beta = store.create_entity(workspace_id, canonical_label="Beta")
    sid = store.add_open_statement(
        workspace_id,
        subject_id=alpha,
        surface_phrase="partners",
        object_entity_id=beta,
        object_value=None,
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="partners",
    )
    with store._lock:
        store._conn.execute(
            "UPDATE statements SET recorded_at = ?, invalidated_at = ?, status = 'invalidated' WHERE id = ?",
            ("2022-01-01T00:00:00", "2023-01-01T00:00:00", sid),
        )
        store._conn.execute(
            "UPDATE entities SET created_at = ?, invalidated_at = ? WHERE id = ?",
            ("2022-01-01T00:00:00", "2023-06-01T00:00:00", beta),
        )
        store._conn.commit()

    temporal = build_temporal_graph_from_ledger(store, workspace_id)

    # At 2022-06-01: statement and Beta are both active
    state_mid = temporal.graph.state_at("2022-06-01T00:00:00")
    mid_node_ids = {n["id"] for n in state_mid["nodes"]}
    assert alpha in mid_node_ids
    assert beta in mid_node_ids
    assert any(e.get("edge_type") == "partners" or e.get("type") == "partners" for e in state_mid["edges"])

    # At 2023-03-01: statement invalidated (valid_until=2023-01-01), Beta still active
    state_after_stmt = temporal.graph.state_at("2023-03-01T00:00:00")
    assert not any(
        e.get("edge_type") == "partners" or e.get("type") == "partners"
        for e in state_after_stmt["edges"]
    )
    diff_stmt = diff_graph_states(state_mid, state_after_stmt)
    assert len(diff_stmt["removed_edges"]) == 1

    # At 2024-01-01: Beta entity also invalidated (valid_until=2023-06-01)
    state_after_entity = temporal.graph.state_at("2024-01-01T00:00:00")
    diff_ent = diff_graph_states(state_after_stmt, state_after_entity)
    assert beta in diff_ent["removed_nodes"]
    store.close()


def test_rdf_type_projects_to_existing_class_node_not_literal(tmp_path: Path) -> None:
    workspace_id, store = _workspace_store(tmp_path)
    class_uri = "http://example.org/trellis#Artifact"
    entity_id = store.create_entity(workspace_id, canonical_label="prd-md")
    preserve = GraphSession()
    preserve.add_node(class_uri, "owl:Class", content="Artifact")

    from basis.domain.knowledge.services.entity_type_assign import assign_entity_type

    assign_entity_type(store, workspace_id, subject_id=entity_id, class_uri=class_uri)
    session = rebuild_graph_from_ledger(store, workspace_id, preserve_from=preserve)
    edges = graph_projection_signature(session)["edges"]
    assert any(src == entity_id and tgt == class_uri for src, tgt, _label in edges)
    assert not any(node_id.startswith("typed:") for node_id in session.graph.nodes)
    store.close()
