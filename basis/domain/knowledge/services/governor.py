"""Agent governor batch pass (F-GOV-04 Phase A)."""

from __future__ import annotations

from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.services.conflict_review import run_shacl_conflict_scan
from basis.domain.knowledge.governance_config import DEFAULT_GOVERNOR_CONFIDENCE_MIN
from basis.domain.knowledge.services.governor_cluster import scan_entity_label_clusters
from basis.domain.knowledge.conflict.scan_context import ConflictScanContext
from basis.domain.knowledge.store import KnowledgeStore

LOW_CONFIDENCE_KIND = "low_confidence"
LOW_CONFIDENCE_SUBJECT_TYPE = "statement"


def scan_low_confidence_statements(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    confidence_min: float,
) -> dict[str, Any]:
    """Enqueue open review items for active statements below ``confidence_min``."""
    if not 0.0 <= confidence_min <= 1.0:
        raise AdminError(422, "bad_confidence_min", "confidence_min 须在 0–1 之间")
    created: list[str] = []
    skipped = 0
    for row in knowledge.list_active_statements_below_confidence(workspace_id, confidence_min):
        statement_id = str(row["statement_id"])
        try:
            item = knowledge.create_review_item(
                workspace_id,
                kind=LOW_CONFIDENCE_KIND,
                subject_type=LOW_CONFIDENCE_SUBJECT_TYPE,
                subject_id=statement_id,
                payload={
                    "statement_id": statement_id,
                    "subject_id": row.get("subject_id"),
                    "surface_phrase": row.get("surface_phrase"),
                    "confidence": row.get("confidence"),
                    "confidence_min": confidence_min,
                    "status": row.get("status"),
                },
                priority=3,
            )
            created.append(item["id"])
        except AdminError as exc:
            if exc.code == "review_exists":
                skipped += 1
                continue
            raise
    return {"created": len(created), "skipped": skipped, "item_ids": created}


def run_governor_pass(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    confidence_min: float | None = None,
    scan_ctx: ConflictScanContext | None = None,
    include_shacl: bool = True,
    include_low_confidence: bool = True,
    include_entity_label_clusters: bool = True,
) -> dict[str, Any]:
    """Run selected governor scans (on-demand)."""
    if confidence_min is None:
        threshold = knowledge.get_governance_config(workspace_id).governor_confidence_min
    else:
        threshold = confidence_min
    if include_shacl:
        shacl_scan = run_shacl_conflict_scan(knowledge, workspace_id, scan_ctx=scan_ctx)
    else:
        shacl_scan = {"created": 0, "skipped": 0, "materialize": {"facts_created": 0}, "shacl": {}}
    if include_low_confidence:
        low_confidence = scan_low_confidence_statements(
            knowledge,
            workspace_id,
            confidence_min=threshold,
        )
    else:
        low_confidence = {"created": 0, "skipped": 0}
    if include_entity_label_clusters:
        entity_clusters = scan_entity_label_clusters(knowledge, workspace_id)
    else:
        entity_clusters = {"created": 0, "skipped": 0}
    return {
        "confidence_min": threshold,
        "shacl_scan": {
            "created": shacl_scan.get("created", 0),
            "skipped": shacl_scan.get("skipped", 0),
            "hub_created": (shacl_scan.get("shacl") or {}).get("hub_created", 0),
            "facts_materialized": (shacl_scan.get("materialize") or {}).get("facts_created", 0),
        },
        "low_confidence": {
            "created": low_confidence.get("created", 0),
            "skipped": low_confidence.get("skipped", 0),
        },
        "entity_clusters": {
            "created": entity_clusters.get("created", 0),
            "skipped": entity_clusters.get("skipped", 0),
        },
    }


def resolve_low_confidence_approve(
    knowledge: KnowledgeStore,
    workspace_id: str,
    statement_id: str,
) -> dict[str, Any]:
    """Accept a low-confidence statement (confirm if still pending)."""
    row = knowledge.get_statement_browse(workspace_id, statement_id=statement_id)
    if row is None:
        raise AdminError(404, "not_found", "陈述不存在或已失效")
    if row.get("status") == "pending":
        knowledge.set_statement_status(workspace_id, statement_id, "confirmed")
    return {"statement_id": statement_id, "action": "confirmed"}


def resolve_low_confidence_reject(
    knowledge: KnowledgeStore,
    workspace_id: str,
    statement_id: str,
) -> dict[str, Any]:
    """Reject a low-confidence statement."""
    knowledge.invalidate_statement(workspace_id, statement_id)
    return {"statement_id": statement_id, "action": "invalidated"}
