"""Build forward-chaining fact strings from materialized typed facts."""

from __future__ import annotations

from basis.services.knowledge.store import KnowledgeStore


def predicate_local_name(predicate_uri: str) -> str:
    uri = (predicate_uri or "").strip()
    if uri.startswith("urn:basis:pred:"):
        return uri.removeprefix("urn:basis:pred:")
    if uri.startswith("urn:"):
        return uri.rsplit(":", 1)[-1]
    return uri


def ground_fact_strings_from_typed_facts(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    limit: int = 200,
) -> list[str]:
    """Turn ledger typed_facts into `predicate(Subject, Object)` strings for reasoning/run."""
    labels = {
        row["entity_id"]: row["canonical_label"]
        for row in knowledge.list_active_entity_id_labels(workspace_id)
    }
    out: list[str] = []
    seen: set[str] = set()
    for row in knowledge.list_typed_facts(workspace_id, limit=limit):
        pred = predicate_local_name(str(row.get("predicate_uri") or ""))
        if not pred:
            continue
        subj = labels.get(row["subject_id"]) or str(row["subject_id"])
        object_entity_id = row.get("object_entity_id")
        if object_entity_id:
            obj = labels.get(object_entity_id) or str(object_entity_id)
        else:
            obj = str(row.get("object_value") or "").strip()
        if not subj or not obj:
            continue
        fact = f"{pred}({subj}, {obj})"
        if fact in seen:
            continue
        seen.add(fact)
        out.append(fact)
    return out
