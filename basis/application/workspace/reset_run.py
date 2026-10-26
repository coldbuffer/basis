"""Run workspace reset (sync or job-tracked)."""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any

from basis.application.kernel import WorkspaceCoreContext
from basis.domain.errors import AdminError
from basis.domain.knowledge.persistence.sql_processing_jobs import fetch_job_row
from basis.domain.knowledge.persistence.sql_workspace_reset_job import (
    fetch_active_workspace_reset_job,
    insert_workspace_reset_job,
    mark_workspace_reset_failed,
    mark_workspace_reset_running,
    mark_workspace_reset_succeeded,
)
from basis.domain.knowledge.services.workspace_reset_scopes import (
    DEFAULT_RESET_SCOPES,
    SCOPE_GRAPH,
    SCOPE_KNOWLEDGE,
    normalize_reset_scopes,
    scopes_for_api,
)
from basis.domain.tenancy.admin.admin_types import utc_now_iso

logger = logging.getLogger(__name__)


def _apply_reset_body(
    ctx: WorkspaceCoreContext,
    workspace_id: str,
    scopes: frozenset[str],
    *,
    retain_job_id: str | None,
) -> dict[str, Any]:
    retain: tuple[str, ...] = (retain_job_id,) if retain_job_id else ()
    cleared = ctx.knowledge.execute_workspace_reset(
        workspace_id,
        scopes,
        retain_job_ids=retain,
    )
    if SCOPE_KNOWLEDGE in scopes and ctx.chunk_search is not None:
        ctx.chunk_search.clear_workspace_vectors(workspace_id)
    projection = None
    if SCOPE_GRAPH in scopes:
        if ctx.clear_projection is not None:
            ctx.clear_projection()
        if ctx.rebuild_projection is not None:
            projection = ctx.rebuild_projection()
    return {"cleared": cleared, "scopes": scopes_for_api(scopes), "projection": projection}


def _scopes_from_job_options(ctx: WorkspaceCoreContext, job_id: str) -> frozenset[str]:
    wid = ctx.workspace.id
    with ctx.knowledge._lock:
        row = fetch_job_row(ctx.knowledge._conn, wid, job_id)
    opts = row.options if isinstance(row.options, dict) else {}
    raw = opts.get("scopes")
    scopes = normalize_reset_scopes(raw)
    return scopes if scopes is not None else DEFAULT_RESET_SCOPES


def schedule_workspace_reset_job(ctx: WorkspaceCoreContext, job_id: str) -> None:
    """Run reset job off the request thread (HTTP/MCP async enqueue)."""

    def _run() -> None:
        try:
            run_workspace_reset_job(ctx, job_id)
        except Exception:
            logger.exception("workspace_reset job %s failed", job_id)

    threading.Thread(target=_run, daemon=True, name=f"workspace-reset-{job_id[:8]}").start()


def enqueue_workspace_reset_job(
    ctx: WorkspaceCoreContext,
    scopes: frozenset[str],
) -> dict[str, Any]:
    wid = ctx.workspace.id
    with ctx.knowledge._lock:
        conn = ctx.knowledge._conn
        active = fetch_active_workspace_reset_job(conn, wid)
        if active is not None:
            return {
                "accepted": True,
                "job_id": active["id"],
                "status": active["status"],
                "duplicate": True,
            }
        job_id = str(uuid.uuid4())
        now = utc_now_iso()
        insert_workspace_reset_job(
            conn,
            job_id=job_id,
            workspace_id=wid,
            now=now,
            actor_id=ctx.user.id,
            scopes=scopes_for_api(scopes),
        )
        conn.commit()
    return {"accepted": True, "job_id": job_id, "status": "queued", "duplicate": False}


def run_workspace_reset_job(ctx: WorkspaceCoreContext, job_id: str) -> dict[str, Any]:
    wid = ctx.workspace.id
    now = utc_now_iso()
    try:
        with ctx.knowledge._lock:
            conn = ctx.knowledge._conn
            mark_workspace_reset_running(conn, wid, job_id, now)
            conn.commit()
        scopes = _scopes_from_job_options(ctx, job_id)
        outcome = _apply_reset_body(ctx, wid, scopes, retain_job_id=job_id)
        with ctx.store._lock:
            ctx.store._audit(
                ctx.user.id,
                "workspace.reset",
                "workspace",
                wid,
                {
                    "cleared": outcome["cleared"],
                    "scopes": outcome.get("scopes"),
                    "job_id": job_id,
                },
            )
            ctx.store._conn.commit()
        with ctx.knowledge._lock:
            conn = ctx.knowledge._conn
            mark_workspace_reset_succeeded(
                conn,
                wid,
                job_id,
                finished_at=utc_now_iso(),
                result={"ok": True, "workspace_id": wid, **outcome},
            )
            conn.commit()
        return {"ok": True, "workspace_id": wid, "job_id": job_id, **outcome}
    except Exception as exc:
        message = str(exc)
        code = exc.code if isinstance(exc, AdminError) else "reset_failed"
        with ctx.knowledge._lock:
            conn = ctx.knowledge._conn
            mark_workspace_reset_failed(
                conn,
                wid,
                job_id,
                code=code,
                message=message,
                finished_at=utc_now_iso(),
            )
            conn.commit()
        raise
