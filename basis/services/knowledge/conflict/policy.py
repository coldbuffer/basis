"""Predicate cardinality policy for statement conflict detection."""

from __future__ import annotations

from typing import Any

# Surfaces where multiple objects per (subject, predicate) are expected (ingest noise reduction).
_MULTI_VALUED_PREDICATE_SURFACES: frozenset[str] = frozenset(
    {
        "contains",
        "includes",
        "has",
        "has part",
        "has_part",
        "haspart",
        "part of",
        "part_of",
        "partof",
        "member of",
        "member_of",
        "composed of",
        "consists of",
        "mentions",
        "references",
        "links to",
        "related to",
        "relates to",
        "associated with",
        "connected to",
    }
)

CONFLICT_SCHEMA_VERSION = 2


def normalize_surface(phrase: str) -> str:
    return " ".join((phrase or "").strip().lower().split())


def _surface_matches_multi_valued_heuristic(surface_norm: str) -> bool:
    if surface_norm in _MULTI_VALUED_PREDICATE_SURFACES:
        return True
    for token in ("contains", "includes", "mentions", "references"):
        if surface_norm == token or surface_norm.endswith(f":{token}") or surface_norm.endswith(f" {token}"):
            return True
    return False


def build_property_mapping_index(
    mappings: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Map normalized signature → confirmed property mapping row."""
    index: dict[str, dict[str, Any]] = {}
    for row in mappings:
        if str(row.get("target_kind") or "") != "property":
            continue
        if str(row.get("status") or "") != "confirmed":
            continue
        sig = normalize_surface(str(row.get("signature") or ""))
        if sig:
            index[sig] = row
    return index


def resolve_predicate_policy(
    surface_phrase: str,
    mapping_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Whether multiple active objects are allowed and how the predicate was resolved."""
    surface_norm = normalize_surface(surface_phrase)
    mapping = mapping_index.get(surface_norm)
    if mapping and mapping.get("target_uri"):
        allows_multiple = _surface_matches_multi_valued_heuristic(surface_norm)
        return {
            "surface_normalized": surface_norm,
            "predicate_iri": str(mapping["target_uri"]),
            "allows_multiple_objects": allows_multiple,
        }
    allows_multiple = _surface_matches_multi_valued_heuristic(surface_norm)
    return {
        "surface_normalized": surface_norm,
        "predicate_iri": None,
        "allows_multiple_objects": allows_multiple,
    }
