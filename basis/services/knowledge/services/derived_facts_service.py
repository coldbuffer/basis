"""Persist reasoning output to derived_facts / fact_derivations (F-RUL-03)."""

from __future__ import annotations

from typing import Any

from basis.services.graph.reasoning.forward import _parse_fact
from basis.services.knowledge.store import KnowledgeStore


def _predicate_uri(predicate: str) -> str:
    clean = predicate.strip()
    if clean.startswith("http://") or clean.startswith("https://") or clean.startswith("urn:"):
        return clean
    return f"urn:basis:pred:{clean}"


def _resolve_rule_id(knowledge: KnowledgeStore, workspace_id: str, rule_text: str) -> str | None:
    body = (rule_text or "").strip()
    if not body:
        return None
    for row in knowledge.list_reasoning_rules(workspace_id, limit=500):
        if (row.get("body") or "").strip() == body:
            return row["id"]
    return None


def persist_reasoning_derived(
    knowledge: KnowledgeStore,
    workspace_id: str,
    proof_chains: list[dict[str, Any]],
) -> dict[str, Any]:
    """Record derived facts for each proof chain conclusion (binary facts only)."""
    created_ids: list[str] = []
    skipped = 0
    for chain in proof_chains:
        conclusion = str(chain.get("conclusion") or "").strip()
        parsed = _parse_fact(conclusion)
        if parsed is None:
            skipped += 1
            continue
        predicate, args = parsed
        if len(args) != 2:
            skipped += 1
            continue
        subject_id = knowledge.get_or_create_entity_by_label(workspace_id, args[0])
        object_entity_id = knowledge.get_or_create_entity_by_label(workspace_id, args[1])
        rule_id = _resolve_rule_id(knowledge, workspace_id, str(chain.get("rule") or ""))
        premises = [str(p).strip() for p in (chain.get("premises") or []) if str(p).strip()]
        derivations = [("ground_fact", p[:240]) for p in premises]
        fact_id = knowledge.insert_derived_fact(
            workspace_id,
            subject_id=subject_id,
            predicate_uri=_predicate_uri(predicate),
            object_entity_id=object_entity_id,
            object_value=None,
            rule_id=rule_id,
            derivations=derivations,
        )
        if fact_id:
            created_ids.append(fact_id)
        else:
            skipped += 1
    return {"created": len(created_ids), "skipped": skipped, "ids": created_ids}
