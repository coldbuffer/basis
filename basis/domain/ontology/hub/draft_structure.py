"""Extract ontology schema edges (subClassOf, domain, range) from editor draft diffs."""

from __future__ import annotations

from typing import Any

from basis.domain.ontology.hub.draft_apply import as_draft_mapping

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
