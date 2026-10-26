"""Ontology hub graph reads (search, subgraph, entity detail)."""

from __future__ import annotations

from typing import Any

from basis.domain.ontology.hub.catalog import _classify_node_type, _node_label
from basis.domain.ontology.browse.graph_scope import (
    GraphTruncationError,
    collect_core_nodes,
    known_ontology_uris,
    resolve_owning_ontology,
    searchable_node_types,
    select_structure_edges,
)
from basis.domain.ontology.browse.preview_read import extract_namespace
from basis.domain.errors import AdminError


def search_entities(
    session: Any,
    *,
    q: str,
    entity_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if not q or not str(q).strip():
        raise AdminError(422, "validation_error", "Query parameter q is required.")
    limit = max(1, min(int(limit), 200))
    searchable = searchable_node_types()
    raw_hits = session.search(q, limit * 6)
    results: list[dict[str, Any]] = []

    for hit in raw_hits:
        node = hit.get("node", hit)
        ntype = node.get("type", "")
        if ntype not in searchable:
            continue
        etype = _classify_node_type(ntype)
        if entity_type and etype != entity_type:
            continue

        label = _node_label(node)
        props = node.get("properties", {})
        definition = (
            props.get("rdfs:comment")
            or props.get("skos:definition")
            or props.get("description")
        )

        results.append(
            {
                "uri": node.get("id", ""),
                "label": label,
                "type": ntype,
                "entity_type": etype,
                "definition": definition,
                "source_ontology": props.get("scheme_uri"),
                "namespace_prefix": extract_namespace(node.get("id", "")),
            }
        )
        if len(results) >= limit:
            break

    return results


def get_ontology_graph(
    session: Any,
    registry: dict[str, Any],
    *,
    uri: str,
    versions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not uri or not str(uri).strip():
        raise AdminError(422, "validation_error", "Query parameter uri is required.")

    known = known_ontology_uris(session, registry)
    if uri not in known:
        raise AdminError(404, "not_found", "Ontology not found in registry.")

    try:
        core_nodes_by_id = collect_core_nodes(session, uri, known, versions=versions)
        if not core_nodes_by_id:
            raise AdminError(404, "not_found", "Ontology graph not found.")
        core_node_ids = set(core_nodes_by_id)
        selected_edges = select_structure_edges(session, core_node_ids)
    except GraphTruncationError as exc:
        raise AdminError(413, "payload_too_large", str(exc)) from exc

    external_node_ids = {
        node_id
        for edge in selected_edges
        for node_id in (str(edge.get("source", "")), str(edge.get("target", "")))
    } - core_node_ids
    external_nodes = [session.get_node(node_id) for node_id in external_node_ids]

    selected_nodes = list(core_nodes_by_id.values())
    selected_nodes.extend(node for node in external_nodes if node is not None)
    selected_nodes.sort(key=lambda node: str(node.get("id", "")))
    selected_edges.sort(
        key=lambda edge: (
            str(edge.get("source", "")),
            str(edge.get("type", "")),
            str(edge.get("target", "")),
            str(edge.get("id", "")),
        )
    )
    return {
        "uri": uri,
        "nodes": [
            {**node, "entity_type": _classify_node_type(node.get("type", ""))}
            for node in selected_nodes
        ],
        "edges": selected_edges,
    }


def get_entity_detail(
    session: Any,
    registry: dict[str, Any],
    *,
    entity_uri: str,
) -> dict[str, Any]:
    node = session.get_node(entity_uri)
    if node is None:
        raise AdminError(404, "not_found", "Entity not found.")

    props = node.get("properties", {})
    ntype = node.get("type", "")
    label = _node_label(node)
    definition = props.get("rdfs:comment") or props.get("skos:definition") or props.get("description")

    out_edges, _ = session.get_edges(source=entity_uri, skip=0, limit=9999)
    in_edges, _ = session.get_edges(target=entity_uri, skip=0, limit=9999)

    superclasses = [e["target"] for e in out_edges if e.get("type") in {"rdfs:subClassOf", "skos:broader"}]
    subclasses = [e["source"] for e in in_edges if e.get("type") in {"rdfs:subClassOf", "skos:broader"}]
    domain = [e["target"] for e in out_edges if e.get("type") == "rdfs:domain"]
    range_ = [e["target"] for e in out_edges if e.get("type") == "rdfs:range"]

    all_nodes, _ = session.get_nodes(skip=0, limit=999_999)
    instance_count = sum(1 for n in all_nodes if n.get("type") == entity_uri)
    known = known_ontology_uris(session, registry)

    return {
        "uri": entity_uri,
        "label": label,
        "type": ntype,
        "entity_type": _classify_node_type(ntype),
        "definition": definition,
        "source_ontology": props.get("scheme_uri"),
        "owning_ontology": resolve_owning_ontology(node, known),
        "superclasses": superclasses,
        "subclasses": subclasses,
        "domain": domain,
        "range": range_,
        "instance_count": instance_count,
        "properties": props,
    }
