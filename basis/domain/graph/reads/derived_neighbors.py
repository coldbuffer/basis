"""Merge ledger derived_facts into graph neighbor lists for entity nodes."""

from __future__ import annotations

from typing import Any

from basis.domain.knowledge.reasoning_ground_facts import predicate_local_name
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.ontology.mappings.access import RDF_TYPE_URI


def merge_derived_fact_neighbors(
    knowledge: KnowledgeStore,
    workspace_id: str,
    entity_id: str,
    neighbors: list[dict[str, Any]],
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Append ledger typed/derived facts not already present in projected graph neighbors."""
    labels = {
        row["entity_id"]: row["canonical_label"]
        for row in knowledge.list_active_entity_id_labels(workspace_id)
    }
    seen = {
        (str(n.get("id") or ""), str(n.get("relationship") or n.get("edge_type") or ""))
        for n in neighbors
    }
    merged = list(neighbors)

    typed_rows = knowledge.list_typed_facts_for_subject(workspace_id, entity_id, limit=limit)
    for fact in typed_rows:
        relationship = predicate_local_name(str(fact.get("predicate_uri") or ""))
        if not relationship:
            continue
        object_entity_id = fact.get("object_entity_id")
        if object_entity_id:
            target_id = str(object_entity_id)
            content = labels.get(target_id) or target_id
            node_type = "entity"
        else:
            target_id = str(fact.get("object_value") or "").strip() or f"typed:{fact['id']}"
            content = target_id
            node_type = "literal" if fact.get("predicate_uri") != RDF_TYPE_URI else "class"
        key = (target_id, relationship)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "id": target_id,
                "type": node_type,
                "content": content,
                "relationship": relationship,
                "weight": float(fact.get("confidence") or 1.0),
                "hop": 1,
                "projection_layer": "typed",
                "typed_fact_id": fact["id"],
            }
        )

    if not knowledge.ledger_entity_exists(workspace_id, entity_id):
        return merged

    derived_rows = knowledge.list_derived_facts_for_entity(workspace_id, entity_id, limit=limit)
    if not derived_rows:
        return merged

    for fact in derived_rows:
        relationship = predicate_local_name(str(fact.get("predicate_uri") or ""))
        if not relationship:
            continue
        object_entity_id = fact.get("object_entity_id")
        if object_entity_id:
            target_id = str(object_entity_id)
            content = labels.get(target_id) or target_id
            node_type = "entity"
        else:
            target_id = f"derived:{fact['id']}"
            content = str(fact.get("object_value") or "").strip()
            node_type = "literal"
        key = (target_id, relationship)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                "id": target_id,
                "type": node_type,
                "content": content,
                "relationship": relationship,
                "weight": 1.0,
                "hop": 1,
                "projection_layer": "derived",
                "derived_fact_id": fact["id"],
            }
        )
    return merged
