"""Sync typed facts from confirmed property mappings before conflict detection."""

from __future__ import annotations

from typing import Any

from basis.domain.knowledge.store import KnowledgeStore


def materialize_confirmed_property_mappings(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    mapping_limit: int = 500,
) -> dict[str, Any]:
    """Materialize ledger statements into typed_facts for confirmed property and class mappings."""
    mappings = knowledge.list_mappings(workspace_id, status="confirmed", limit=mapping_limit)
    mappings_processed = 0
    facts_created = 0
    for row in mappings:
        if str(row.get("target_kind") or "") not in {"property", "class"}:
            continue
        mapping_id = str(row.get("id") or "").strip()
        if not mapping_id:
            continue
        result = knowledge.materialize_mapping_facts(workspace_id, mapping_id)
        mappings_processed += 1
        facts_created += int(result.get("created") or 0)
    return {
        "mappings_processed": mappings_processed,
        "facts_created": facts_created,
    }
