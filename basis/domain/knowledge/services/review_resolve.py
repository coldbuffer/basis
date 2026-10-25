"""Sync review resolution helpers for integration core (MCP / HTTP)."""

from __future__ import annotations

from typing import Any, Callable

from basis.domain.errors import AdminError
from basis.domain.graph.projection.projection_lifecycle import (
    GraphProjectionBindings,
    rebuild_graph_projection,
)
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.ports.platform import WorkspaceAuditActor, WorkspaceAuditStore
from basis.domain.knowledge.services.graph_audit import audit_graph
from basis.domain.knowledge.services.conflict_review import SHACL_VIOLATION_KIND, run_shacl_conflict_scan
from basis.domain.knowledge.services.governor import LOW_CONFIDENCE_KIND, resolve_low_confidence_reject
from basis.domain.knowledge.services.governor_cluster import ENTITY_CLUSTER_KIND
from basis.domain.knowledge.services.import_review import discard_staged_import
from basis.domain.ontology.mappings.service import (
    MAPPING_REVIEW_KIND,
    apply_mapping_status_change,
)
from basis.domain.knowledge.services.remember_service import STATEMENT_REVIEW_KIND

from basis.domain.knowledge.store import KnowledgeStore


def approve_statement_remember_review(
    *,
    knowledge: KnowledgeStore,
    store: WorkspaceAuditStore,
    user: WorkspaceAuditActor,
    workspace_id: str,
    item_id: str,
    rationale: str | None,
    rebuild_projection: Callable[[], Any] | None = None,
    audit_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Approve an open ``statement_remember`` review item (MCP / core parity with console)."""
    item = knowledge.get_review_item(workspace_id, item_id)
    if item["status"] != "open":
        raise AdminError(409, "review_closed", "审核项已处理")
    if item.get("kind") != STATEMENT_REVIEW_KIND:
        raise AdminError(422, "unsupported_review_kind", f"不支持的审核类型: {item.get('kind')}")
    payload = item.get("payload") or {}
    statement_id = str(payload.get("statement_id") or item["subject_id"])
    knowledge.set_statement_status(workspace_id, statement_id, "confirmed")
    if rebuild_projection is not None:
        rebuild_projection()
    merge_result = {
        "statement_id": statement_id,
        "status": "confirmed",
        "shacl_scan": run_shacl_conflict_scan(knowledge, workspace_id),
    }
    resolved = knowledge.resolve_review_item(
        workspace_id,
        item_id,
        status="approved",
        resolved_by=user.id,
        rationale=rationale,
    )
    audit_extra_merged: dict[str, Any] = {"merge": merge_result, "rationale": rationale}
    if audit_extra:
        audit_extra_merged.update(audit_extra)
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.statement.remember_approved",
        review_item_id=item_id,
        extra=audit_extra_merged,
    )
    return {"item": resolved, "merge": merge_result}


def reject_statement_remember_review(
    *,
    knowledge: KnowledgeStore,
    store: WorkspaceAuditStore,
    user: WorkspaceAuditActor,
    workspace_id: str,
    item_id: str,
    rationale: str | None,
) -> dict[str, Any]:
    """Reject an open ``statement_remember`` review item."""
    item = knowledge.get_review_item(workspace_id, item_id)
    if item["status"] != "open":
        raise AdminError(409, "review_closed", "审核项已处理")
    if item.get("kind") != STATEMENT_REVIEW_KIND:
        raise AdminError(422, "unsupported_review_kind", f"不支持的审核类型: {item.get('kind')}")
    payload = item.get("payload") or {}
    statement_id = str(payload.get("statement_id") or item["subject_id"])
    knowledge.set_statement_status(workspace_id, statement_id, "rejected")
    resolved = knowledge.resolve_review_item(
        workspace_id,
        item_id,
        status="rejected",
        resolved_by=user.id,
        rationale=rationale,
    )
    audit_graph(
        store,
        user,
        workspace_id,
        "workspace.statement.remember_rejected",
        review_item_id=item_id,
        extra={"rationale": rationale, "payload": item.get("payload")},
    )
    return {"item": resolved}


def reject_review_item(
    *,
    knowledge: KnowledgeStore,
    store: WorkspaceAuditStore,
    user: WorkspaceAuditActor,
    workspace_id: str,
    item_id: str,
    rationale: str | None,
    blob_store: BlobStore | None = None,
    projection_bindings: GraphProjectionBindings | None = None,
) -> dict[str, Any]:
    """Reject an open review item (HTTP / future MCP parity)."""
    item = knowledge.get_review_item(workspace_id, item_id)
    kind = item.get("kind")
    if kind == "graph_import":
        if blob_store is None:
            raise AdminError(500, "internal_error", "blob store required for graph import reject")
        discard_staged_import(blob_store, workspace_id, item.get("payload") or {})
    elif kind == MAPPING_REVIEW_KIND:
        payload = item.get("payload") or {}
        mapping_id = str(payload.get("mapping_id") or item["subject_id"])
        apply_mapping_status_change(
            workspace_id,
            mapping_id,
            user,
            store,
            knowledge,
            status="rejected",
            why=rationale,
            sync_review=False,
            projection_bindings=projection_bindings,
        )
    elif kind == STATEMENT_REVIEW_KIND:
        return reject_statement_remember_review(
            knowledge=knowledge,
            store=store,
            user=user,
            workspace_id=workspace_id,
            item_id=item_id,
            rationale=rationale,
        )
    elif kind == "connector_writeback":
        outbox_id = str((item.get("payload") or {}).get("outbox_id") or item["subject_id"])
        knowledge.reject_entity_sync_outbox(workspace_id, outbox_id)
    resolved = knowledge.resolve_review_item(
        workspace_id,
        item_id,
        status="rejected",
        resolved_by=user.id,
        rationale=rationale,
    )
    if kind == "graph_import":
        reject_action = "workspace.graph.import_rejected"
    elif kind == MAPPING_REVIEW_KIND:
        reject_action = "workspace.mapping.rejected"
    elif kind == STATEMENT_REVIEW_KIND:
        reject_action = "workspace.statement.remember_rejected"
    elif kind == SHACL_VIOLATION_KIND:
        reject_action = "workspace.shacl.violation_dismissed"
    elif kind == ENTITY_CLUSTER_KIND:
        reject_action = "workspace.entity.cluster_dismissed"
    elif kind == LOW_CONFIDENCE_KIND:
        payload = dict(item.get("payload") or {})
        statement_id = str(payload.get("statement_id") or item["subject_id"])
        resolve_low_confidence_reject(knowledge, workspace_id, statement_id)
        if projection_bindings is not None:
            rebuild_graph_projection(projection_bindings, workspace_id)
        reject_action = "workspace.statement.low_confidence_rejected"
    else:
        reject_action = "workspace.graph.merge_rejected"
    audit_graph(
        store,
        user,
        workspace_id,
        reject_action,
        review_item_id=item_id,
        extra={"rationale": rationale, "payload": item.get("payload")},
    )
    return {"item": resolved}
