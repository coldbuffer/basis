"""Ontology editor draft structure validation and graph application."""

from __future__ import annotations


# ── draft_structure.py ──
"""Extract ontology schema edges (subClassOf, domain, range) from editor draft diffs."""


from typing import Any


_SUBCLASS_AXIOM_TYPES = frozenset({
    "subClassOf",
    "rdfs:subClassOf",
    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
})

def _diff_list(diff: Any, key: str) -> list[Any]:
    if diff is None:
        return []
    if hasattr(diff, key):
        return list(getattr(diff, key) or [])
    if isinstance(diff, dict):
        return list(diff.get(key) or [])
    return []


def _diff_dict(diff: Any, key: str) -> dict[str, Any]:
    if diff is None:
        return {}
    if hasattr(diff, key):
        raw = getattr(diff, key)
        return dict(raw or {}) if isinstance(raw, dict) else {}
    if isinstance(diff, dict):
        raw = diff.get(key) or {}
        return dict(raw) if isinstance(raw, dict) else {}
    return {}


def _uri_values(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            text = str(item or "").strip()
            if text:
                out.append(text)
        return out
    text = str(raw).strip()
    return [text] if text else []


def _is_subclass_axiom(axiom_type: str) -> bool:
    return axiom_type.strip() in _SUBCLASS_AXIOM_TYPES


def _axiom_endpoints(axiom_map: dict[str, Any]) -> tuple[str, str]:
    subject = str(
        axiom_map.get("subject")
        or axiom_map.get("source")
        or axiom_map.get("class_uri")
        or ""
    ).strip()
    object_uri = str(
        axiom_map.get("object")
        or axiom_map.get("value")
        or axiom_map.get("target")
        or axiom_map.get("superclass")
        or axiom_map.get("parent")
        or ""
    ).strip()
    return subject, object_uri


def _edge_dict(source: str, target: str, edge_type: str, weight: float = 1.0) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "type": edge_type,
        "weight": weight,
    }


def structure_edges_from_diff(diff: Any) -> list[dict[str, Any]]:
    """All schema edges implied by a draft diff (for publish and impact counts)."""
    edges: list[dict[str, Any]] = []

    for raw_edge in _diff_list(diff, "added_edges"):
        edge_map = as_draft_mapping(raw_edge)
        source = str(edge_map.get("source", "")).strip()
        target = str(edge_map.get("target", "")).strip()
        edge_type = str(edge_map.get("type", "")).strip()
        if not source or not target or not edge_type:
            continue
        edges.append(
            _edge_dict(
                source,
                target,
                edge_type,
                float(edge_map.get("weight", 1.0) or 1.0),
            )
        )

    for raw_axiom in _diff_list(diff, "added_axioms"):
        axiom_map = as_draft_mapping(raw_axiom)
        axiom_type = str(axiom_map.get("type", "")).strip()
        subject, object_uri = _axiom_endpoints(axiom_map)
        if _is_subclass_axiom(axiom_type) and subject and object_uri:
            edges.append(_edge_dict(subject, object_uri, "rdfs:subClassOf"))
            continue
        if axiom_type in {"owl:inverseOf", "http://www.w3.org/2002/07/owl#inverseOf"}:
            if subject and object_uri:
                edges.append(_edge_dict(subject, object_uri, "owl:inverseOf"))

    for class_uri, changes in _diff_dict(diff, "modified_classes").items():
        subject = str(class_uri or "").strip()
        if not subject:
            continue
        change_map = as_draft_mapping(changes)
        for key in ("subClassOf", "rdfs:subClassOf", "superclass", "parent"):
            for parent in _uri_values(change_map.get(key)):
                edges.append(_edge_dict(subject, parent, "rdfs:subClassOf"))

    for prop_uri, changes in _diff_dict(diff, "modified_properties").items():
        source = str(prop_uri or "").strip()
        if not source:
            continue
        change_map = as_draft_mapping(changes)
        for key, edge_type in (("domain", "rdfs:domain"), ("rdfs:domain", "rdfs:domain")):
            for target in _uri_values(change_map.get(key)):
                edges.append(_edge_dict(source, target, edge_type))
        for key, edge_type in (("range", "rdfs:range"), ("rdfs:range", "rdfs:range")):
            for target in _uri_values(change_map.get(key)):
                edges.append(_edge_dict(source, target, edge_type))

    return edges


def structure_change_summary(diff: Any) -> dict[str, int]:
    edges = structure_edges_from_diff(diff)
    subclass = sum(1 for e in edges if e.get("type") == "rdfs:subClassOf")
    domain = sum(1 for e in edges if e.get("type") == "rdfs:domain")
    range_ = sum(1 for e in edges if e.get("type") == "rdfs:range")
    other = len(edges) - subclass - domain - range_
    return {
        "edge_adds": len(_diff_list(diff, "added_edges")),
        "axiom_adds": len(_diff_list(diff, "added_axioms")),
        "structure_edge_total": len(edges),
        "subclass_edges": subclass,
        "domain_edges": domain,
        "range_edges": range_,
        "other_structure_edges": other,
    }

# ── draft_apply.py ──
"""Apply ontology editor draft diffs onto a workspace graph session."""


import logging
import uuid
from typing import Any

from basis.services.ontology.hub.registry_scope import find_edge_ids_for_triple, parse_edge_removal_ref
from basis.services.ontology.hub.registry_scope import RestrictionKindSpec, restriction_spec

logger = logging.getLogger(__name__)


def as_draft_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {}


def _session_graph(session: Any) -> Any | None:
    return getattr(session, "graph", None)


def _purge_node(session: Any, node_id: str) -> bool:
    graph = _session_graph(session)
    if graph is None or not node_id:
        return False
    if not graph.find_node(node_id):
        return False
    if hasattr(graph, "purge_node"):
        return bool(graph.purge_node(node_id))
    if hasattr(graph, "add_node_attribute"):
        graph.add_node_attribute(node_id, {"status": "archived"})
        return True
    return False


def _purge_edge(session: Any, edge_id: str) -> bool:
    graph = _session_graph(session)
    if graph is None or not edge_id:
        return False
    if hasattr(graph, "purge_edge"):
        return bool(graph.purge_edge(edge_id))
    if hasattr(graph, "retract_edge"):
        return bool(graph.retract_edge(edge_id))
    return False


def _purge_edge_ref(session: Any, ref: str) -> bool:
    """Remove by runtime edge id or by ``source|type|target`` fallback key."""
    token = str(ref or "").strip()
    if not token:
        return False
    if _purge_edge(session, token):
        return True
    triple = parse_edge_removal_ref(token)
    if triple is None:
        return False
    graph = _session_graph(session)
    if graph is None:
        return False
    removed = False
    for edge_id in find_edge_ids_for_triple(graph, *triple):
        if _purge_edge(session, edge_id):
            removed = True
    return removed


def _restriction_namespace(ontology_uri: str) -> str:
    stem = str(ontology_uri).rstrip("/#")
    if stem.endswith("#ontology"):
        stem = stem[: -len("#ontology")].rstrip("/#")
    return stem or ontology_uri


def _parse_cardinality(data: dict[str, Any]) -> int | None:
    raw = data.get("cardinality")
    if raw is None:
        raw = data.get("cardinality_value")
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _filler_uri(data: dict[str, Any], spec: RestrictionKindSpec) -> str:
    if spec.filler_role == "class":
        return str(
            data.get("filler_class") or data.get("onClass") or data.get("value") or ""
        ).strip()
    if spec.filler_role == "individual":
        return str(
            data.get("filler_individual") or data.get("has_value") or data.get("value") or ""
        ).strip()
    if spec.filler_role == "datatype":
        return str(
            data.get("filler_datatype") or data.get("onDataRange") or data.get("value") or ""
        ).strip()
    return ""


def _literal_value(data: dict[str, Any]) -> str:
    return str(data.get("literal_value") or data.get("value") or "").strip()


def _build_restriction_node_properties(
    data: dict[str, Any],
    spec: RestrictionKindSpec,
    on_property: str,
) -> dict[str, Any] | None:
    props: dict[str, Any] = {"owl:onProperty": on_property}

    if spec.cardinality_mode == "unqualified":
        cardinality = _parse_cardinality(data)
        if cardinality is None:
            return None
        props[spec.owl_predicate] = cardinality
        return props

    if spec.cardinality_mode == "qualified":
        cardinality = _parse_cardinality(data)
        filler = _filler_uri(data, spec)
        if cardinality is None or not filler:
            return None
        props[spec.owl_predicate] = cardinality
        if spec.filler_role == "datatype":
            props["owl:onDataRange"] = filler
        else:
            props["owl:onClass"] = filler
        return props

    if spec.filler_role == "literal":
        literal = _literal_value(data)
        if not literal:
            return None
        props[spec.owl_predicate] = literal
        datatype = str(data.get("filler_datatype") or data.get("onDataRange") or "").strip()
        if datatype:
            props["owl:datatype"] = datatype
        return props

    filler = _filler_uri(data, spec)
    if not filler:
        return None
    props[spec.owl_predicate] = filler
    return props


def materialize_restrictions(
    ontology_uri: str,
    restrictions: list[Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    ns = _restriction_namespace(ontology_uri)
    for raw in restrictions:
        data = as_draft_mapping(raw)
        restriction_type = str(data.get("type", "")).strip()
        property_scope = str(data.get("property_scope") or data.get("scope") or "object").strip()
        spec = restriction_spec(property_scope, restriction_type)
        if spec is None:
            logger.debug("Skipping unknown restriction type: %s (%s)", restriction_type, property_scope)
            continue
        class_uri = str(data.get("class_uri") or data.get("subject") or "").strip()
        on_property = str(data.get("onProperty") or "").strip()
        if not class_uri or not on_property:
            continue
        node_props = _build_restriction_node_properties(data, spec, on_property)
        if node_props is None:
            continue

        restriction_uri = f"{ns}/_restriction/{uuid.uuid4().hex[:12]}"
        nodes.append(
            {
                "id": restriction_uri,
                "type": "owl:Restriction",
                "content": "",
                "properties": node_props,
            }
        )
        edges.append(
            {
                "source": class_uri,
                "target": restriction_uri,
                "type": "rdfs:subClassOf",
                "weight": 1.0,
            }
        )
        edges.append(
            {
                "source": restriction_uri,
                "target": on_property,
                "type": "owl:onProperty",
                "weight": 1.0,
            }
        )
        if spec.filler_edge_type:
            filler_target = ""
            if spec.filler_role == "literal":
                filler_target = str(node_props.get(spec.owl_predicate) or "")
            else:
                filler_target = _filler_uri(data, spec)
            if filler_target:
                edges.append(
                    {
                        "source": restriction_uri,
                        "target": filler_target,
                        "type": spec.filler_edge_type,
                        "weight": 1.0,
                    }
                )
    return nodes, edges


def apply_removals(
    session: Any,
    diff: Any,
    *,
    diff_list: Any,
) -> tuple[int, int]:
    """Archive/purge nodes and edges listed in the draft diff. Returns (nodes_removed, edges_removed)."""
    nodes_removed = 0
    edges_removed = 0
    for edge_id in diff_list(diff, "removed_edges"):
        if _purge_edge_ref(session, str(edge_id)):
            edges_removed += 1
    for node_id in diff_list(diff, "removed_classes"):
        if _purge_node(session, str(node_id)):
            nodes_removed += 1
    for node_id in diff_list(diff, "removed_properties"):
        if _purge_node(session, str(node_id)):
            nodes_removed += 1
    for node_id in diff_list(diff, "removed_individuals"):
        if _purge_node(session, str(node_id)):
            nodes_removed += 1
    return nodes_removed, edges_removed
