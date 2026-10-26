from basis.domain.graph.projection.projector import rebuild_graph_from_ledger
from basis.domain.graph.projection.session import GraphSession
from basis.domain.tenancy.admin.store import AdminStore
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.store import KnowledgeStore


def _workspace_store(tmp_path):
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("schema-preserve@example.com", "password1", "U")
    workspace_id = admin.create_workspace(user, "KB", None, "restricted").id
    admin.close()
    store = KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))
    return workspace_id, store


def test_rebuild_preserves_only_enabled_ontology_schema(tmp_path) -> None:
    workspace_id, knowledge = _workspace_store(tmp_path)
    onto_a = "https://example.org/onto-a#"
    onto_b = "https://example.org/onto-b#"
    class_a = f"{onto_a}ClassA"
    class_b = f"{onto_b}ClassB"

    prior = GraphSession()
    prior.add_node(
        class_a,
        "owl:Class",
        content="ClassA",
        scheme_uri=onto_a,
    )
    prior.add_node(
        class_b,
        "owl:Class",
        content="ClassB",
        scheme_uri=onto_b,
    )

    registry = {
        onto_a: {"uri": onto_a, "enabled": True},
        onto_b: {"uri": onto_b, "enabled": False},
    }

    session = rebuild_graph_from_ledger(
        knowledge,
        workspace_id,
        preserve_from=prior,
        ontology_registry=registry,
    )

    assert session.graph.find_node(class_a) is not None
    assert session.graph.find_node(class_b) is None
    knowledge.close()


def test_rebuild_without_registry_preserves_all_schema(tmp_path) -> None:
    workspace_id, knowledge = _workspace_store(tmp_path)
    onto = "https://example.org/onto#"
    class_id = f"{onto}Thing"

    prior = GraphSession()
    prior.add_node(class_id, "owl:Class", content="Thing", scheme_uri=onto)

    session = rebuild_graph_from_ledger(
        knowledge,
        workspace_id,
        preserve_from=prior,
        ontology_registry=None,
    )

    assert session.graph.find_node(class_id) is not None
    knowledge.close()
