"""SHACL conflict scan entry (mapped ledger assertions)."""

from __future__ import annotations

from typing import Any

from basis.domain.knowledge.conflict.scan_context import ConflictScanContext
from basis.domain.knowledge.store import KnowledgeStore


def run_shacl_conflict_scan(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    scan_ctx: ConflictScanContext | None = None,
) -> dict[str, Any]:
    """Materialize mappings and enqueue SHACL violations for mapped functional predicates."""
    from basis.domain.knowledge.conflict.materialize import materialize_confirmed_property_mappings
    from basis.domain.knowledge.conflict.shacl_scan import scan_shacl_violations

    materialize = materialize_confirmed_property_mappings(knowledge, workspace_id)
    shacl = scan_shacl_violations(knowledge, workspace_id, scan_ctx=scan_ctx)
    return {
        "created": shacl.get("created", 0),
        "skipped": shacl.get("skipped", 0),
        "item_ids": shacl.get("item_ids", []),
        "materialize": materialize,
        "shacl": shacl,
    }
