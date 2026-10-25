"""Copy graph-only entities and edges into the evidence ledger.

ContextGraph edits that never wrote a statement would disappear the next time
the projection is rebuilt. ``save_graph`` calls this first so those nodes and
edges become ledger rows, which the projector can draw again.
"""

from __future__ import annotations

import uuid
from typing import Any

from basis.domain.graph.projection.session import GraphSession
from basis.domain.knowledge.store import KnowledgeStore

GRAPH_SYNC_DOC_ID = "__basis_graph_sync__"
GRAPH_SYNC_PROPOSED_BY = "graph_sync"
_SKIP_NODE_TYPES = frozenset({"document", "literal", "owl:Ontology", "projection_meta"})
_LEDGER_EDGE_KEYS = ("statement_id", "typed_fact_id", "derived_fact_id")
_LEDGER_LAYERS = frozenset({"ledger", "open", "typed", "derived"})


def _props(obj: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    properties = getattr(obj, "properties", None)
    metadata = getattr(obj, "metadata", None)
    if isinstance(properties, dict):
        merged.update(properties)
    if isinstance(metadata, dict):
        merged.update(metadata)
    return merged


def _display_label(node: Any) -> str:
    """Human-facing label for ledger ``canonical_label`` (never the graph node id)."""
    content = getattr(node, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()[:500]
    for key in ("name", "label", "text", "rdfs:label"):
        value = _props(node).get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
    return ""


def _label(node: Any) -> str:
    """Best-effort label for literals and legacy callers (may fall back to node id)."""
    display = _display_label(node)
    if display:
        return display
    return str(getattr(node, "node_id", "")).strip()[:500]


def _is_ledger_entity_id(knowledge: KnowledgeStore, workspace_id: str, value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return knowledge.ledger_entity_exists(workspace_id, value)


def _stamp_ledger_entity_link(
    session: GraphSession, node_id: str, ledger_entity_id: str
) -> None:
    graph = session.graph
    if hasattr(graph, "add_node_attribute"):
        graph.add_node_attribute(node_id, {"ledger_entity_id": ledger_entity_id})
        return
    node = graph.nodes.get(node_id)
    if node is None:
        return
    props = _props(node)
    props["ledger_entity_id"] = ledger_entity_id
    content = getattr(node, "content", None)
    graph.add_node(
        node_id,
        str(getattr(node, "node_type", "") or "entity"),
        content=content if isinstance(content, str) else None,
        **props,
    )


def _collapse_slug_entity_duplicate(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    display_entity_id: str,
    graph_node_id: str,
) -> None:
    """Merge a mistaken slug ``canonical_label`` row into the display-label entity."""
    slug = graph_node_id.strip()
    if not slug or slug == display_entity_id:
        return
    slug_entity_id = knowledge.find_entity_id_by_label(workspace_id, slug)
    if slug_entity_id is None or slug_entity_id == display_entity_id:
        return
    redirect = knowledge.entity_merge_redirect(workspace_id)
    if slug_entity_id in redirect:
        return
    knowledge.record_entity_merge(
        workspace_id,
        source_entity_id=slug_entity_id,
        target_entity_id=display_entity_id,
        actor_id=None,
        why="graph_sync: collapse duplicate entity keyed by graph node id",
    )


def _skip_node(node: Any) -> bool:
    node_type = str(getattr(node, "node_type", "") or "")
    node_id = str(getattr(node, "node_id", "") or "")
    if node_type in _SKIP_NODE_TYPES or ":" in node_type:
        return True
    return node_id.startswith(("literal:", "typed:", "derived:"))


def _edges(session: GraphSession) -> list[Any]:
    edges = session.graph.edges
    if isinstance(edges, dict):
        return list(edges.values())
    return list(edges)


def _edge_already_ledgered(edge: Any) -> bool:
    meta = _props(edge)
    if any(meta.get(key) for key in _LEDGER_EDGE_KEYS):
        return True
    layer = meta.get("projection_layer")
    return isinstance(layer, str) and layer in _LEDGER_LAYERS


def resolve_ledger_entity_id(
    knowledge: KnowledgeStore,
    workspace_id: str,
    session: GraphSession,
    node_id: str,
) -> str | None:
    """Return the ledger entity for a graph node, creating one when the node is new."""
    if _is_ledger_entity_id(knowledge, workspace_id, node_id):
        return node_id
    node = session.graph.nodes.get(node_id)
    if node is None or _skip_node(node):
        return None
    meta = _props(node)
    ledger_id = meta.get("ledger_entity_id")
    if isinstance(ledger_id, str) and knowledge.ledger_entity_exists(workspace_id, ledger_id):
        return ledger_id

    display = _display_label(node)
    slug = str(node_id).strip()
    if display:
        entity_id = knowledge.get_or_create_entity_by_label(workspace_id, display)
        if slug and slug != display:
            _collapse_slug_entity_duplicate(
                knowledge,
                workspace_id,
                display_entity_id=entity_id,
                graph_node_id=slug,
            )
    elif slug and slug != "unknown":
        entity_id = knowledge.get_or_create_entity_by_label(workspace_id, slug)
    else:
        return None

    _stamp_ledger_entity_link(session, node_id, entity_id)
    return entity_id


def _sync_chunk(knowledge: KnowledgeStore, workspace_id: str) -> str:
    doc = next(
        (row for row in knowledge.list_documents(workspace_id) if row.get("doc_id") == GRAPH_SYNC_DOC_ID),
        None,
    )
    if doc is None:
        outcome = knowledge.store_document_bytes(
            workspace_id,
            title="Graph edits",
            mime_type="text/plain",
            data=b"(synthetic anchor for facts written from the graph projection)\n",
            created_by=None,
            external_key=GRAPH_SYNC_DOC_ID,
        )
        knowledge.set_version_status(workspace_id, outcome.version_id, "ready")
        return knowledge.create_chunk(
            workspace_id,
            outcome.version_id,
            ordinal=0,
            text="Facts added from the graph projection are anchored here.",
        )
    version_id = doc.get("version_id")
    if not version_id:
        raise RuntimeError("graph sync anchor document has no version")
    if doc.get("version_status") != "ready":
        knowledge.set_version_status(workspace_id, version_id, "ready")
    chunks = knowledge.list_chunks_for_version(workspace_id, version_id)
    if chunks:
        return chunks[0]["id"]
    return knowledge.create_chunk(
        workspace_id,
        version_id,
        ordinal=0,
        text="Facts added from the graph projection are anchored here.",
    )


def sync_graph_to_ledger(
    knowledge: KnowledgeStore,
    workspace_id: str,
    session: GraphSession,
) -> dict[str, int]:
    """Insert ledger entities and pending statements for graph rows that have none."""
    entity_ids: dict[str, str] = {}
    for node in session.graph.nodes.values():
        if _skip_node(node):
            continue
        entity_id = resolve_ledger_entity_id(knowledge, workspace_id, session, node.node_id)
        if entity_id is None:
            continue
        entity_ids[node.node_id] = entity_id

    entities_created = 0
    for node in session.graph.nodes.values():
        if node.node_id not in entity_ids:
            continue
        linked = _props(node).get("ledger_entity_id")
        if isinstance(linked, str) and linked == entity_ids[node.node_id]:
            continue
        if _is_ledger_entity_id(knowledge, workspace_id, node.node_id):
            continue
        if isinstance(linked, str) and knowledge.ledger_entity_exists(workspace_id, linked):
            continue
        entities_created += 1

    statements_created = 0
    chunk_id: str | None = None
    for edge in _edges(session):
        if getattr(edge, "edge_type", None) == "mentioned_in" or _edge_already_ledgered(edge):
            continue
        source_id = edge.source_id
        target_id = edge.target_id
        subject = entity_ids.get(source_id)
        if subject is None:
            continue
        surface = str(getattr(edge, "edge_type", "") or "related_to").strip() or "related_to"
        target_node = session.graph.nodes.get(target_id)
        object_entity_id: str | None = entity_ids.get(target_id)
        object_value: str | None = None
        if object_entity_id is None and target_node is not None and not _skip_node(target_node):
            continue
        if object_entity_id is None:
            if target_node is None or str(getattr(target_node, "node_type", "")) != "literal":
                continue
            if str(target_id).startswith(("literal:", "typed:", "derived:")):
                continue
            object_value = _label(target_node) or None
            if not object_value:
                continue
        if knowledge.has_equivalent_statement(
            workspace_id,
            subject,
            surface,
            object_entity_id=object_entity_id,
            object_value=object_value,
        ):
            continue
        if chunk_id is None:
            chunk_id = _sync_chunk(knowledge, workspace_id)
        knowledge.add_open_statement(
            workspace_id,
            subject_id=subject,
            surface_phrase=surface,
            object_entity_id=object_entity_id,
            object_value=object_value,
            status="pending",
            proposed_by=GRAPH_SYNC_PROPOSED_BY,
            chunk_id=chunk_id,
            quote=surface,
        )
        statements_created += 1

    return {
        "entities_created": entities_created,
        "statements_created": statements_created,
    }
