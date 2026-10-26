"""Stable references for removing ontology structure edges (id or source|type|target)."""

from __future__ import annotations

from typing import Any

EDGE_REF_SEP = "|"


def edge_removal_ref(source: str, edge_type: str, target: str) -> str:
    return f"{source.strip()}{EDGE_REF_SEP}{edge_type.strip()}{EDGE_REF_SEP}{target.strip()}"


def parse_edge_removal_ref(ref: str) -> tuple[str, str, str] | None:
    text = str(ref or "").strip()
    if EDGE_REF_SEP not in text:
        return None
    parts = text.split(EDGE_REF_SEP, 2)
    if len(parts) != 3:
        return None
    source, edge_type, target = (part.strip() for part in parts)
    if not source or not edge_type or not target:
        return None
    return source, edge_type, target


def find_edge_ids_for_triple(graph: Any, source: str, edge_type: str, target: str) -> list[str]:
    if graph is None or not hasattr(graph, "find_edges"):
        return []
    matches: list[str] = []
    for edge in graph.find_edges():
        if not isinstance(edge, dict):
            continue
        if (
            str(edge.get("source") or "") == source
            and str(edge.get("target") or "") == target
            and str(edge.get("type") or "") == edge_type
        ):
            edge_id = str(edge.get("id") or "").strip()
            if edge_id:
                matches.append(edge_id)
    return matches
