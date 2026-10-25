"""Minimal RDF/Turtle for mapped ledger assertions (SHACL validation slice)."""

from __future__ import annotations

from typing import Any

ENTITY_URN_PREFIX = "urn:basis:entity:"


def entity_node_iri(entity_id: str) -> str:
    return f"{ENTITY_URN_PREFIX}{entity_id}"


def entity_id_from_node_iri(node: str | None) -> str | None:
    if not node:
        return None
    text = str(node).strip().strip("<>")
    if text.startswith(ENTITY_URN_PREFIX):
        return text[len(ENTITY_URN_PREFIX) :]
    return None


def build_mapped_assertions(
    rows: list[dict[str, Any]],
    mapping_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    from basis.domain.knowledge.conflict.policy import normalize_surface, resolve_predicate_policy

    assertions: list[dict[str, Any]] = []
    for row in rows:
        surface_phrase = str(row.get("surface_phrase") or "")
        policy = resolve_predicate_policy(surface_phrase, mapping_index)
        predicate_iri = policy.get("predicate_iri")
        if not predicate_iri:
            continue
        assertions.append(
            {
                "statement_id": row.get("statement_id"),
                "subject_id": row["subject_id"],
                "predicate_iri": predicate_iri,
                "object_entity_id": row.get("object_entity_id"),
                "object_value": row.get("object_value"),
            }
        )
    return assertions


def assertions_to_data_graph_turtle(assertions: list[dict[str, Any]]) -> str:
    lines = ["@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
    for item in assertions:
        subject = f"<{entity_node_iri(str(item['subject_id']))}>"
        pred = f"<{item['predicate_iri']}>"
        if item.get("object_entity_id"):
            obj = f"<{entity_node_iri(str(item['object_entity_id']))}>"
        elif item.get("object_value") is not None:
            raw = str(item["object_value"]).replace("\\", "\\\\").replace('"', '\\"')
            obj = f'"{raw}"'
        else:
            continue
        lines.append(f"{subject} {pred} {obj} .")
    return "\n".join(lines) + ("\n" if lines else "")
