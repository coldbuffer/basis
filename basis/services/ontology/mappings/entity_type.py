"""Entity (class) mapping — type-relation phrases and object-label matching."""

from __future__ import annotations

import json
from typing import Any, Sequence

DEFAULT_ENTITY_TYPE_SURFACE_PHRASES: tuple[str, ...] = (
    "是",
    "instance_of",
    "is_a",
    "is a",
    "type",
    "rdf:type",
)


def normalize_object_label(value: str | None) -> str:
    return (value or "").strip().casefold()


def entity_type_surface_phrases_from_config(config: Any) -> tuple[str, ...]:
    raw = getattr(config, "entity_type_surface_phrases_json", None)
    if not raw:
        return DEFAULT_ENTITY_TYPE_SURFACE_PHRASES
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return DEFAULT_ENTITY_TYPE_SURFACE_PHRASES
    if not isinstance(parsed, list):
        return DEFAULT_ENTITY_TYPE_SURFACE_PHRASES
    phrases = tuple(str(p).strip() for p in parsed if str(p).strip())
    return phrases or DEFAULT_ENTITY_TYPE_SURFACE_PHRASES


def object_label_from_statement_row(row: Any) -> str:
    object_value = row["object_value"] if "object_value" in row.keys() else None
    if object_value is not None and str(object_value).strip():
        return str(object_value).strip()
    entity_label = row["object_entity_label"] if "object_entity_label" in row.keys() else None
    if entity_label is not None and str(entity_label).strip():
        return str(entity_label).strip()
    return ""


def statement_matches_object_label(row: Any, object_label: str) -> bool:
    if not object_label.strip():
        return False
    candidate = object_label_from_statement_row(row)
    if not candidate:
        return False
    return normalize_object_label(candidate) == normalize_object_label(object_label)


def filter_type_phrases(phrases: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        clean = str(phrase).strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out
