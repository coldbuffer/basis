from pathlib import Path

from basis.services.tenancy.admin.store import AdminStore
from basis.services.graph.projection.projector import graph_projection_signature, rebuild_graph_from_ledger
from basis.services.knowledge.blob_store import BlobStore
from basis.services.knowledge.store import KnowledgeStore


def _fixture_merge_entities(store: KnowledgeStore, workspace_id: str, actor_id: str) -> tuple[str, str]:
    _, version_id, _, _ = store.store_upload_bytes(
        workspace_id,
        title="t.txt",
        mime_type="text/plain",
        data=b"x",
        created_by=None,
        external_key="doc-merge",
    )
    chunk_id = store.create_chunk(workspace_id, version_id, ordinal=0, text="Alice knows Bob.")
    store.set_version_status(workspace_id, version_id, "ready")
    alice = store.create_entity(workspace_id, canonical_label="Alice")
    bob = store.create_entity(workspace_id, canonical_label="Bob")
    store.add_open_statement(
        workspace_id,
        subject_id=alice,
        surface_phrase="knows",
        object_entity_id=bob,
        object_value=None,
        status="confirmed",
        proposed_by="test",
        chunk_id=chunk_id,
        quote="knows Bob",
    )
    return alice, bob


def test_active_merge_collapses_entity_nodes(tmp_path: Path) -> None:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("mp@example.com", "password1", "U")
    workspace_id = admin.create_workspace(user, "KB", None, "restricted").id
    actor_id = user.id
    admin.close()

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    alice, bob = _fixture_merge_entities(store, workspace_id, actor_id)

    before = rebuild_graph_from_ledger(store, workspace_id)
    assert bob in graph_projection_signature(before)["node_ids"]

    store.record_entity_merge(
        workspace_id,
        source_entity_id=bob,
        target_entity_id=alice,
        actor_id=actor_id,
    )
    after = rebuild_graph_from_ledger(store, workspace_id)
    node_ids = graph_projection_signature(after)["node_ids"]
    assert bob not in node_ids
    assert alice in node_ids
    edges = graph_projection_signature(after)["edges"]
    assert any(edge[0] == alice and edge[1] == alice for edge in edges)
    store.close()


def test_revert_merge_restores_distinct_entities(tmp_path: Path) -> None:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("rv@example.com", "password1", "U")
    workspace_id = admin.create_workspace(user, "KB", None, "restricted").id
    actor_id = user.id
    admin.close()

    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    alice, bob = _fixture_merge_entities(store, workspace_id, actor_id)
    row = store.record_entity_merge(
        workspace_id,
        source_entity_id=bob,
        target_entity_id=alice,
        actor_id=actor_id,
    )
    store.revert_entity_merge(workspace_id, row["id"], reverted_by=actor_id)

    session = rebuild_graph_from_ledger(store, workspace_id)
    node_ids = graph_projection_signature(session)["node_ids"]
    assert alice in node_ids and bob in node_ids
    store.close()
