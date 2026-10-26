"""Rebuild ContextGraph snapshots from the canonical knowledge ledger."""

from __future__ import annotations

from typing import Any

from basis.domain.graph.projection.session import GraphSession
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.ontology.hub.registry_scope import should_preserve_schema_node

PROJECTION_SCHEMA_VERSION = 1
_LEDGER_NODE_TYPES = frozenset({"document", "literal", "entity", "projection_meta"})
RDF_TYPE_URI = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _node_type_value(node: Any) -> str:
    if isinstance(node, dict):
        return str(node.get("type") or node.get("node_type") or "")
    return str(getattr(node, "node_type", "") or "")


def _is_schema_projection_node(node: Any) -> bool:
    """OWL/RDF/SKOS nodes live in the graph snapshot, not the evidence ledger."""
    node_type = _node_type_value(node)
    if node_type in _LEDGER_NODE_TYPES:
        return False
    return ":" in node_type


def _is_rdf_type_predicate(predicate_uri: str) -> bool:
    probe = str(predicate_uri or "").strip()
    return probe == RDF_TYPE_URI or _predicate_edge_label(probe) == "type"


def _resolve_schema_object_node_id(session: GraphSession, predicate_uri: str, object_value: str) -> str | None:
    """Link typed/derived facts to existing OWL/SKOS nodes when object_value is that node id."""
    if not _is_rdf_type_predicate(predicate_uri):
        return None
    uri = str(object_value or "").strip()
    if not uri:
        return None
    raw = session.graph.find_node(uri)
    if raw is None or not _is_schema_projection_node(raw):
        return None
    return uri


def _object_target_id_for_fact(
    session: GraphSession,
    *,
    fact_id: str,
    predicate_uri: str,
    object_entity_id: str | None,
    object_value: str | None,
    merge_redirect: dict[str, str],
    projection_layer: str,
    node_id_prefix: str,
    recorded_at: str | None,
    invalidated_at: str | None = None,
    extra_node_props: dict[str, Any],
) -> str | None:
    if object_entity_id:
        return _canon_entity_id(object_entity_id, merge_redirect)
    if not object_value:
        return None
    linked = _resolve_schema_object_node_id(session, predicate_uri, str(object_value))
    if linked:
        return linked
    target_id = f"{node_id_prefix}:{fact_id}"
    session.add_node(
        target_id,
        "literal",
        content=str(object_value),
        projection_layer=projection_layer,
        **extra_node_props,
        **({"valid_from": recorded_at} if recorded_at else {}),
        **({"valid_until": invalidated_at} if invalidated_at else {}),
    )
    return target_id


def _predicate_edge_label(predicate_uri: str) -> str:
    cleaned = (predicate_uri or "").strip().rstrip("/#")
    if not cleaned:
        return "related_to"
    if "/" in cleaned:
        return cleaned.rsplit("/", 1)[-1] or cleaned
    if ":" in cleaned:
        return cleaned.rsplit(":", 1)[-1] or cleaned
    return cleaned


def _copy_preserved_nodes(
    source: GraphSession,
    target: GraphSession,
    *,
    ontology_registry: dict[str, Any] | None = None,
    ontology_published_entity_uris: set[str] | None = None,
) -> None:
    preserved_ids: set[str] = set()
    for node in source.graph.nodes.values():
        if not _is_schema_projection_node(node):
            continue
        node_type = _node_type_value(node)
        if not should_preserve_schema_node(
            node,
            node_type,
            ontology_registry,
            published_entity_uris=ontology_published_entity_uris,
        ):
            continue
        props = dict(node.properties) if isinstance(node.properties, dict) else {}
        props.pop("content", None)
        target.add_node(
            node.node_id,
            node.node_type,
            content=node.content,
            **props,
        )
        preserved_ids.add(node.node_id)

    edges = source.graph.edges
    edge_values = edges.values() if isinstance(edges, dict) else edges
    for edge in edge_values:
        if edge.source_id not in preserved_ids or edge.target_id not in preserved_ids:
            continue
        props: dict[str, Any] = {}
        for key in ("properties", "metadata"):
            raw = getattr(edge, key, None)
            if isinstance(raw, dict):
                props.update(raw)
        target.add_edge(edge.source_id, edge.target_id, edge.edge_type, **props)


def _edge_signature(session: GraphSession) -> list[tuple[str, str, str]]:
    edges = session.graph.edges
    if isinstance(edges, dict):
        values = edges.values()
    else:
        values = edges
    return sorted(
        (edge.source_id, edge.target_id, edge.edge_type)
        for edge in values
    )


def graph_projection_signature(session: GraphSession) -> dict[str, Any]:
    """Stable summary for tests and migration checks."""
    return {
        "node_ids": sorted(session.graph.nodes.keys()),
        "edges": _edge_signature(session),
        "node_count": len(session.graph.nodes),
        "edge_count": len(_edge_signature(session)),
    }


def _canon_entity_id(entity_id: str, merge_redirect: dict[str, str]) -> str:
    return merge_redirect.get(entity_id, entity_id)


def _earliest_iso(current: str | None, candidate: str | None) -> str | None:
    if not candidate:
        return current
    if not current:
        return candidate
    return min(str(current), str(candidate))


def _note_entity_first_seen(
    seen: dict[str, str],
    entity_id: str | None,
    at: str | None,
    *,
    merge_redirect: dict[str, str],
) -> None:
    if not entity_id or not at:
        return
    canon = _canon_entity_id(entity_id, merge_redirect)
    seen[canon] = _earliest_iso(seen.get(canon), at) or str(at)


def _entity_valid_from(
    entity_id: str,
    *,
    entity_first_seen: dict[str, str],
    entity_created_at: str | None,
) -> str | None:
    """First ledger appearance drives graph-diff ``state_at``; fall back to row creation."""
    return entity_first_seen.get(entity_id) or entity_created_at


def _build_entity_first_seen(
    knowledge: KnowledgeStore,
    workspace_id: str,
    merge_redirect: dict[str, str],
    *,
    include_invalidated: bool = False,
) -> dict[str, str]:
    seen: dict[str, str] = {}
    statements = (
        knowledge.list_statements_for_temporal_projection(workspace_id)
        if include_invalidated
        else knowledge.list_statements_for_projection(workspace_id)
    )
    typed_facts = (
        knowledge.list_typed_facts_for_temporal_projection(workspace_id)
        if include_invalidated
        else knowledge.list_typed_facts_for_projection(workspace_id)
    )
    derived_facts = (
        knowledge.list_derived_facts_for_temporal_projection(workspace_id)
        if include_invalidated
        else knowledge.list_derived_facts_for_projection(workspace_id)
    )
    for row in statements:
        at = row.get("recorded_at")
        _note_entity_first_seen(seen, row["subject_id"], at, merge_redirect=merge_redirect)
        _note_entity_first_seen(seen, row.get("object_entity_id"), at, merge_redirect=merge_redirect)
    for fact in typed_facts:
        at = fact.get("recorded_at")
        _note_entity_first_seen(seen, fact["subject_id"], at, merge_redirect=merge_redirect)
        _note_entity_first_seen(seen, fact.get("object_entity_id"), at, merge_redirect=merge_redirect)
    for fact in derived_facts:
        at = fact.get("recorded_at")
        _note_entity_first_seen(seen, fact["subject_id"], at, merge_redirect=merge_redirect)
        _note_entity_first_seen(seen, fact.get("object_entity_id"), at, merge_redirect=merge_redirect)
    return seen


def build_temporal_graph_from_ledger(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    preserve_from: GraphSession | None = None,
) -> GraphSession:
    """Build a temporal ContextGraph including invalidated rows with `valid_until` (F-TIM-01–04)."""
    merge_redirect = knowledge.entity_merge_redirect(workspace_id)
    session = GraphSession()
    if preserve_from is not None:
        _copy_preserved_nodes(preserve_from, session)

    entity_first_seen = _build_entity_first_seen(
        knowledge, workspace_id, merge_redirect, include_invalidated=True
    )

    for doc in knowledge.list_ready_documents_for_projection(workspace_id):
        graph_doc_id = doc["graph_doc_id"]
        text = doc["text"]
        doc_valid_from = doc.get("version_created_at")
        session.add_node(
            graph_doc_id,
            "document",
            content=text,
            text=text,
            ledger_document_id=doc["document_id"],
            ledger_version_id=doc["version_id"],
            projection_layer="ledger",
            projection_schema_version=PROJECTION_SCHEMA_VERSION,
            **({"valid_from": doc_valid_from} if doc_valid_from else {}),
        )

    for entity in knowledge.list_entities_for_temporal_projection(workspace_id):
        if entity["id"] in merge_redirect:
            continue
        label = entity["canonical_label"] or ""
        valid_from = _entity_valid_from(
            entity["id"],
            entity_first_seen=entity_first_seen,
            entity_created_at=entity.get("created_at"),
        )
        valid_until = entity.get("invalidated_at")
        session.add_node(
            entity["id"],
            "entity",
            content=label,
            name=label,
            ledger_entity_id=entity["id"],
            projection_layer="ledger",
            **({"valid_from": valid_from} if valid_from else {}),
            **({"valid_until": valid_until} if valid_until else {}),
        )

    typed_facts = knowledge.list_typed_facts_for_temporal_projection(workspace_id)
    for row in knowledge.list_statements_for_temporal_projection(workspace_id):
        surface = row["surface_phrase"]
        statement_id = row["statement_id"]
        evidence_id = row.get("evidence_id")
        chunk_id = row.get("chunk_id")
        confidence = row.get("confidence")
        graph_doc_id = row.get("graph_doc_id")
        subject_id = _canon_entity_id(row["subject_id"], merge_redirect)
        recorded_at = row.get("recorded_at")
        invalidated_at = row.get("invalidated_at")

        edge_props: dict[str, Any] = {
            "statement_id": statement_id,
            "evidence_id": evidence_id,
            "chunk_id": chunk_id,
            "projection_layer": "open",
            "statement_status": row["status"],
        }
        if confidence is not None:
            edge_props["confidence"] = confidence
        if recorded_at:
            edge_props["valid_from"] = recorded_at
        if invalidated_at:
            edge_props["valid_until"] = invalidated_at

        if row["object_entity_id"]:
            target_id = _canon_entity_id(row["object_entity_id"], merge_redirect)
        elif row["object_value"]:
            target_id = f"literal:{statement_id}"
            session.add_node(
                target_id,
                "literal",
                content=row["object_value"],
                projection_layer="ledger",
                statement_id=statement_id,
                **({"valid_from": recorded_at} if recorded_at else {}),
                **({"valid_until": invalidated_at} if invalidated_at else {}),
            )
        else:
            continue

        session.add_edge(
            subject_id,
            target_id,
            surface,
            **edge_props,
        )
        if graph_doc_id:
            mention_props: dict[str, Any] = {
                "projection_layer": "ledger",
                "chunk_id": chunk_id,
            }
            if recorded_at:
                mention_props["valid_from"] = recorded_at
            if invalidated_at:
                mention_props["valid_until"] = invalidated_at
            session.add_edge(
                subject_id,
                graph_doc_id,
                "mentioned_in",
                **mention_props,
            )

    for fact in typed_facts:
        subject_id = _canon_entity_id(fact["subject_id"], merge_redirect)
        recorded_at = fact.get("recorded_at")
        invalidated_at = fact.get("invalidated_at")
        target_id = _object_target_id_for_fact(
            session,
            fact_id=str(fact["id"]),
            predicate_uri=str(fact["predicate_uri"]),
            object_entity_id=fact.get("object_entity_id"),
            object_value=fact.get("object_value"),
            merge_redirect=merge_redirect,
            projection_layer="typed",
            node_id_prefix="typed",
            recorded_at=recorded_at,
            invalidated_at=invalidated_at,
            extra_node_props={"typed_fact_id": fact["id"]},
        )
        if not target_id:
            continue
        edge_label = _predicate_edge_label(fact["predicate_uri"])
        edge_props: dict[str, Any] = {
            "projection_layer": "typed",
            "typed_fact_id": fact["id"],
            "predicate_uri": fact["predicate_uri"],
        }
        if fact.get("mapping_id"):
            edge_props["mapping_id"] = fact["mapping_id"]
        if fact.get("confidence") is not None:
            edge_props["confidence"] = fact["confidence"]
        if recorded_at:
            edge_props["valid_from"] = recorded_at
        if invalidated_at:
            edge_props["valid_until"] = invalidated_at
        session.add_edge(subject_id, target_id, edge_label, **edge_props)

    for fact in knowledge.list_derived_facts_for_temporal_projection(workspace_id):
        subject_id = _canon_entity_id(fact["subject_id"], merge_redirect)
        recorded_at = fact.get("recorded_at")
        invalidated_at = fact.get("invalidated_at")
        target_id = _object_target_id_for_fact(
            session,
            fact_id=str(fact["id"]),
            predicate_uri=str(fact["predicate_uri"]),
            object_entity_id=fact.get("object_entity_id"),
            object_value=fact.get("object_value"),
            merge_redirect=merge_redirect,
            projection_layer="derived",
            node_id_prefix="derived",
            recorded_at=recorded_at,
            invalidated_at=invalidated_at,
            extra_node_props={"derived_fact_id": fact["id"]},
        )
        if not target_id:
            continue
        edge_label = _predicate_edge_label(fact["predicate_uri"])
        edge_props: dict[str, Any] = {
            "projection_layer": "derived",
            "derived_fact_id": fact["id"],
            "predicate_uri": fact["predicate_uri"],
        }
        if fact.get("rule_id"):
            edge_props["rule_id"] = fact["rule_id"]
        if recorded_at:
            edge_props["valid_from"] = recorded_at
        if invalidated_at:
            edge_props["valid_until"] = invalidated_at
        session.add_edge(subject_id, target_id, edge_label, **edge_props)

    return session


def rebuild_graph_from_ledger(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    preserve_from: GraphSession | None = None,
    include_version_ids: tuple[str, ...] | None = None,
    ontology_registry: dict[str, Any] | None = None,
    ontology_published_entity_uris: set[str] | None = None,
) -> GraphSession:
    """Full rebuild of workspace graph content from ledger rows (ontology nodes may be preserved)."""
    knowledge.ensure_projection_state(workspace_id)
    knowledge.set_projection_status(workspace_id, "building")
    merge_redirect = knowledge.entity_merge_redirect(workspace_id)
    try:
        session = GraphSession()
        if preserve_from is not None:
            _copy_preserved_nodes(
                preserve_from,
                session,
                ontology_registry=ontology_registry,
                ontology_published_entity_uris=ontology_published_entity_uris,
            )

        entity_first_seen = _build_entity_first_seen(knowledge, workspace_id, merge_redirect)

        for doc in knowledge.list_ready_documents_for_projection(
            workspace_id, include_version_ids=include_version_ids
        ):
            graph_doc_id = doc["graph_doc_id"]
            text = doc["text"]
            doc_valid_from = doc.get("version_created_at")
            session.add_node(
                graph_doc_id,
                "document",
                content=text,
                text=text,
                ledger_document_id=doc["document_id"],
                ledger_version_id=doc["version_id"],
                projection_layer="ledger",
                projection_schema_version=PROJECTION_SCHEMA_VERSION,
                **({"valid_from": doc_valid_from} if doc_valid_from else {}),
            )

        for entity in knowledge.list_entities_for_projection(workspace_id):
            if entity["id"] in merge_redirect:
                continue
            label = entity["canonical_label"] or ""
            valid_from = _entity_valid_from(
                entity["id"],
                entity_first_seen=entity_first_seen,
                entity_created_at=entity.get("created_at"),
            )
            session.add_node(
                entity["id"],
                "entity",
                content=label,
                name=label,
                ledger_entity_id=entity["id"],
                projection_layer="ledger",
                **({"valid_from": valid_from} if valid_from else {}),
            )

        typed_triples: set[tuple[str, str, str]] = set()
        for fact in knowledge.list_typed_facts_for_projection(workspace_id):
            subject_id = _canon_entity_id(fact["subject_id"], merge_redirect)
            if fact["object_entity_id"]:
                target_id = _canon_entity_id(fact["object_entity_id"], merge_redirect)
            elif fact["object_value"]:
                target_id = f"typed:{fact['id']}"
            else:
                continue
            typed_triples.add((subject_id, target_id, _predicate_edge_label(fact["predicate_uri"])))

        mentioned: set[tuple[str, str]] = set()
        for row in knowledge.list_statements_for_projection(workspace_id):
            surface = row["surface_phrase"]
            statement_id = row["statement_id"]
            evidence_id = row.get("evidence_id")
            chunk_id = row.get("chunk_id")
            confidence = row.get("confidence")
            graph_doc_id = row.get("graph_doc_id")
            subject_id = _canon_entity_id(row["subject_id"], merge_redirect)
            recorded_at = row.get("recorded_at")

            edge_props: dict[str, Any] = {
                "statement_id": statement_id,
                "evidence_id": evidence_id,
                "chunk_id": chunk_id,
                "projection_layer": "open",
                "statement_status": row["status"],
            }
            if confidence is not None:
                edge_props["confidence"] = confidence

            if row["object_entity_id"]:
                target_id = _canon_entity_id(row["object_entity_id"], merge_redirect)
            elif row["object_value"]:
                target_id = f"literal:{statement_id}"
                session.add_node(
                    target_id,
                    "literal",
                    content=row["object_value"],
                    projection_layer="ledger",
                    statement_id=statement_id,
                    **({"valid_from": recorded_at} if recorded_at else {}),
                )
            else:
                continue

            if (subject_id, target_id, surface) in typed_triples:
                continue

            if recorded_at:
                edge_props["valid_from"] = recorded_at

            session.add_edge(
                subject_id,
                target_id,
                surface,
                **edge_props,
            )
            if graph_doc_id:
                pair = (subject_id, graph_doc_id)
                if pair not in mentioned:
                    mention_props: dict[str, Any] = {
                        "projection_layer": "ledger",
                        "chunk_id": chunk_id,
                    }
                    if recorded_at:
                        mention_props["valid_from"] = recorded_at
                    session.add_edge(
                        subject_id,
                        graph_doc_id,
                        "mentioned_in",
                        **mention_props,
                    )
                    mentioned.add(pair)

        for fact in knowledge.list_typed_facts_for_projection(workspace_id):
            subject_id = _canon_entity_id(fact["subject_id"], merge_redirect)
            recorded_at = fact.get("recorded_at")
            target_id = _object_target_id_for_fact(
                session,
                fact_id=str(fact["id"]),
                predicate_uri=str(fact["predicate_uri"]),
                object_entity_id=fact.get("object_entity_id"),
                object_value=fact.get("object_value"),
                merge_redirect=merge_redirect,
                projection_layer="typed",
                node_id_prefix="typed",
                recorded_at=recorded_at,
                extra_node_props={"typed_fact_id": fact["id"]},
            )
            if not target_id:
                continue
            edge_label = _predicate_edge_label(fact["predicate_uri"])
            edge_props: dict[str, Any] = {
                "projection_layer": "typed",
                "typed_fact_id": fact["id"],
                "predicate_uri": fact["predicate_uri"],
            }
            if fact.get("mapping_id"):
                edge_props["mapping_id"] = fact["mapping_id"]
            if fact.get("confidence") is not None:
                edge_props["confidence"] = fact["confidence"]
            if recorded_at:
                edge_props["valid_from"] = recorded_at
            session.add_edge(subject_id, target_id, edge_label, **edge_props)

        for fact in knowledge.list_derived_facts_for_projection(workspace_id):
            subject_id = _canon_entity_id(fact["subject_id"], merge_redirect)
            recorded_at = fact.get("recorded_at")
            target_id = _object_target_id_for_fact(
                session,
                fact_id=str(fact["id"]),
                predicate_uri=str(fact["predicate_uri"]),
                object_entity_id=fact.get("object_entity_id"),
                object_value=fact.get("object_value"),
                merge_redirect=merge_redirect,
                projection_layer="derived",
                node_id_prefix="derived",
                recorded_at=recorded_at,
                extra_node_props={"derived_fact_id": fact["id"]},
            )
            if not target_id:
                continue
            edge_label = _predicate_edge_label(fact["predicate_uri"])
            edge_props: dict[str, Any] = {
                "projection_layer": "derived",
                "derived_fact_id": fact["id"],
                "predicate_uri": fact["predicate_uri"],
            }
            if fact.get("rule_id"):
                edge_props["rule_id"] = fact["rule_id"]
            if recorded_at:
                edge_props["valid_from"] = recorded_at
            session.add_edge(subject_id, target_id, edge_label, **edge_props)

        knowledge.bump_projection_revision(workspace_id)
        return session
    except Exception:
        knowledge.set_projection_status(workspace_id, "failed", error_code="build_failed")
        raise


def apply_rebuild_to_session(
    knowledge: KnowledgeStore,
    workspace_id: str,
    session: GraphSession,
    *,
    include_version_ids: tuple[str, ...] | None = None,
    ontology_registry: dict[str, Any] | None = None,
    ontology_published_entity_uris: set[str] | None = None,
) -> dict[str, Any]:
    """Replace session graph from ledger; returns build metadata."""
    rebuilt = rebuild_graph_from_ledger(
        knowledge,
        workspace_id,
        preserve_from=session,
        include_version_ids=include_version_ids,
        ontology_registry=ontology_registry,
        ontology_published_entity_uris=ontology_published_entity_uris,
    )
    session.graph = rebuilt.graph
    state = knowledge.get_projection_state(workspace_id)
    return {
        "projection_revision": state["revision"],
        "projection_status": state["status"],
        **session.stats(),
    }
