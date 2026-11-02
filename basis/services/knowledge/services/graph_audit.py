"""Audit helpers for workspace-scoped graph mutations."""

from __future__ import annotations

from typing import Any

from basis.services.knowledge.ports.platform import WorkspaceAuditActor, WorkspaceAuditStore


def audit_graph(
    store: WorkspaceAuditStore,
    actor: WorkspaceAuditActor,
    workspace_id: str,
    action: str,
    *,
    review_item_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    detail: dict[str, Any] = {"workspace_id": workspace_id}
    if review_item_id:
        detail["review_item_id"] = review_item_id
    if extra:
        detail.update(extra)
    store.record_audit(
        actor.id,
        action,
        "workspace",
        workspace_id,
        detail,
    )
