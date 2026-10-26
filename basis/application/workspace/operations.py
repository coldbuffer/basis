"""Workspace meta application services."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext, require_workspace_owner


def op_describe_workspace(ctx: WorkspaceCoreContext, _args: dict[str, Any]) -> dict[str, Any]:
    stats = ctx.knowledge.workspace_mcp_stats(ctx.workspace.id)
    return {
        "workspace_id": ctx.workspace.id,
        "name": ctx.workspace.name,
        "description": ctx.workspace.description,
        **stats,
    }


def op_get_capabilities(ctx: WorkspaceCoreContext, _args: dict[str, Any]) -> dict[str, Any]:
    from basis.application.tool_catalog import TOOL_NAMES
    from basis.infra.runtime.capabilities import workspace_capabilities

    _, role = ctx.store.get_workspace_for(ctx.user, ctx.workspace.id, "viewer")
    payload: dict[str, Any] = {
        "workspace_id": ctx.workspace.id,
        "role": role,
        **workspace_capabilities(role),
        "mcp_tools": list(TOOL_NAMES),
    }
    limits = ctx.runtime_limits
    if limits is not None:
        payload.update(
            {
                "graph_page_max_nodes": limits.graph_page_max_nodes,
                "graph_page_max_edges": limits.graph_page_max_edges,
                "chunk_search_max_limit": limits.chunk_search_max_limit,
                "graph_node_search_max_limit": limits.graph_node_search_max_limit,
                "upload_max_bytes": limits.upload_max_bytes,
                "import_max_bytes": limits.import_max_bytes,
                "ingest_max_inflight": limits.ingest_max_inflight,
                "ingest_max_pending": limits.ingest_max_pending,
                "processing_job_timeout_seconds": limits.processing_job_timeout_seconds,
                "ingest_max_extract_chars": limits.ingest_max_extract_chars,
            }
        )
    return payload


def op_preview_workspace_reset(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    from basis.domain.knowledge.services.workspace_reset_scopes import (
        ALL_RESET_SCOPES,
        DEFAULT_RESET_SCOPES,
        normalize_reset_scopes,
        scopes_for_api,
    )

    require_workspace_owner(ctx)
    wid = ctx.workspace.id
    if "scopes" in args and args.get("scopes") is not None:
        scopes = normalize_reset_scopes(args.get("scopes"))
        if scopes is None:
            return {"error": "invalid_scopes", "message": "Unknown or empty reset scope."}
    else:
        scopes = DEFAULT_RESET_SCOPES
    counts = ctx.knowledge.preview_workspace_reset(wid)
    return {
        "preview": True,
        "workspace_id": wid,
        "workspace_name": ctx.workspace.name,
        "counts": counts,
        "scopes": scopes_for_api(scopes),
        "default_scopes": scopes_for_api(DEFAULT_RESET_SCOPES),
        "available_scopes": scopes_for_api(ALL_RESET_SCOPES),
        "export_pack_path": f"/workspaces/{wid}/graph?export=1",
    }


def _reset_wants_async(args: dict[str, Any]) -> bool:
    if "async" in args:
        return bool(args["async"])
    if "async_mode" in args:
        return bool(args["async_mode"])
    return True


def _validate_reset_confirmation(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> str | None:
    confirmation = str(args.get("confirmation") or "").strip()
    if confirmation != ctx.workspace.name:
        return "confirmation must match the workspace name exactly"
    return None


def op_reset_workspace(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_owner(ctx)
    if bool(args.get("preview")):
        return op_preview_workspace_reset(ctx, args)
    message = _validate_reset_confirmation(ctx, args)
    if message is not None:
        return {"error": "confirmation_required", "message": message}
    from basis.application.workspace.reset_run import (
        _apply_reset_body,
        enqueue_workspace_reset_job,
        run_workspace_reset_job,
        schedule_workspace_reset_job,
    )
    from basis.domain.knowledge.services.workspace_reset_scopes import normalize_reset_scopes

    wid = ctx.workspace.id
    if "scopes" in args and args.get("scopes") is not None:
        scopes = normalize_reset_scopes(args.get("scopes"))
        if scopes is None:
            return {"error": "invalid_scopes", "message": "Unknown or empty reset scope."}
    else:
        scopes = normalize_reset_scopes(None)
        assert scopes is not None
    if _reset_wants_async(args):
        queued = enqueue_workspace_reset_job(ctx, scopes)
        if not queued.get("duplicate"):
            schedule_workspace_reset_job(ctx, str(queued["job_id"]))
        return {
            "accepted": True,
            "workspace_id": wid,
            "scopes": list(sorted(scopes)),
            **queued,
        }
    job_id = str(args.get("job_id") or "").strip()
    if job_id:
        return run_workspace_reset_job(ctx, job_id)
    outcome = _apply_reset_body(ctx, wid, scopes, retain_job_id=None)
    with ctx.store._lock:
        ctx.store._audit(
            ctx.user.id,
            "workspace.reset",
            "workspace",
            wid,
            {"cleared": outcome["cleared"], "scopes": outcome.get("scopes")},
        )
        ctx.store._conn.commit()
    return {"ok": True, "workspace_id": wid, **outcome}


def op_list_processing_jobs(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    status = str(args.get("status") or "").strip() or None
    if status and status not in {"queued", "running", "succeeded", "failed", "cancelled"}:
        return {"error": "invalid status"}
    limit = min(max(1, int(args.get("limit", 100))), 200)
    jobs = ctx.knowledge.list_processing_jobs(ctx.workspace.id, status=status, limit=limit)
    return {"jobs": jobs}
