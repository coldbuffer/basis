"""Review application services."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from basis.application.kernel import WorkspaceCoreContext
from basis.application.kernel import CoreError
from basis.application.kernel import require_workspace_editor
from basis.application.review.deps import review_approve_deps
from basis.application.review.governance_hooks import record_governance_decision_from_context
from basis.domain.errors import AdminError
from basis.domain.knowledge.services.review_resolve import (
    approve_statement_remember_review,
    reject_review_item as reject_review_item_domain,
    reject_statement_remember_review,
)
from basis.domain.knowledge.services.review_resolve_approve import (
    approve_review_item as approve_review_item_domain,
)


def op_list_review_items(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    status = str(args.get("status") or "open").strip() or None
    kind = str(args.get("kind") or "").strip() or None
    limit = min(max(1, int(args.get("limit", 50))), 200)
    offset = max(0, int(args.get("offset", 0)))
    ws = ctx.workspace.id
    total = ctx.knowledge.count_review_items(ws, status=status, kind=kind)
    items = ctx.knowledge.list_review_items(
        ws,
        status=status,
        kind=kind,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": offset + len(items) < total,
    }


def op_get_review_item(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    item_id = str(args.get("item_id", "")).strip()
    if not item_id:
        return {"error": "item_id is required"}
    try:
        item = ctx.knowledge.get_review_item(ctx.workspace.id, item_id)
    except AdminError as exc:
        if exc.code == "not_found":
            return {"error": "review item not found"}
        raise
    return {"item": item}


def op_approve_statement_remember_review(
    ctx: WorkspaceCoreContext,
    args: dict[str, Any],
) -> dict[str, Any]:
    item_id = str(args.get("item_id", "")).strip()
    if not item_id:
        return {"error": "item_id is required"}
    require_workspace_editor(ctx)
    rationale = str(args.get("rationale") or "").strip() or None
    rebuild = ctx.rebuild_projection
    decision_id = record_governance_decision_from_context(
        ctx,
        message="Review approve: statement_remember",
        detail={"item_id": item_id, "source": "mcp"},
    )
    audit_extra = {"decision_id": decision_id} if decision_id else None
    result = approve_statement_remember_review(
        knowledge=ctx.knowledge,
        store=ctx.store,
        user=ctx.user,
        workspace_id=ctx.workspace.id,
        item_id=item_id,
        rationale=rationale,
        rebuild_projection=rebuild,
        audit_extra=audit_extra,
    )
    return {**result, "decision_id": decision_id}


def op_reject_statement_remember_review(
    ctx: WorkspaceCoreContext,
    args: dict[str, Any],
) -> dict[str, Any]:
    item_id = str(args.get("item_id", "")).strip()
    if not item_id:
        return {"error": "item_id is required"}
    require_workspace_editor(ctx)
    rationale = str(args.get("rationale") or "").strip() or None
    return reject_statement_remember_review(
        knowledge=ctx.knowledge,
        store=ctx.store,
        user=ctx.user,
        workspace_id=ctx.workspace.id,
        item_id=item_id,
        rationale=rationale,
    )


def op_approve_review_item(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    item_id = str(args.get("item_id", "")).strip()
    if not item_id:
        return {"error": "item_id is required"}
    require_workspace_editor(ctx)
    rationale = str(args.get("rationale") or "").strip() or None
    primary_id = str(args.get("primary_id") or "").strip() or None
    try:
        deps = review_approve_deps(ctx)
        return asyncio.run(
            approve_review_item_domain(
                knowledge=ctx.knowledge,
                store=ctx.store,
                user=ctx.user,
                workspace_id=ctx.workspace.id,
                item_id=item_id,
                rationale=rationale,
                primary_id_override=primary_id,
                deps=deps,
            )
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        raise CoreError(detail, status_code=exc.status_code) from exc


def op_reject_review_item(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    item_id = str(args.get("item_id", "")).strip()
    if not item_id:
        return {"error": "item_id is required"}
    require_workspace_editor(ctx)
    rationale = str(args.get("rationale") or "").strip() or None
    return reject_review_item_domain(
        knowledge=ctx.knowledge,
        store=ctx.store,
        user=ctx.user,
        workspace_id=ctx.workspace.id,
        item_id=item_id,
        rationale=rationale,
        blob_store=ctx.blob_store,
        projection_bindings=ctx.projection_bindings,
    )
