"""Workspace alert episodes (F-ALT MVP)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import get_current_user, get_workspace_for_editor, get_workspace_for_viewer, get_knowledge_store, get_store
from basis.domain.knowledge.store import KnowledgeStore

router = APIRouter(tags=["workspaces"])


@router.get("/{workspace_id}/alerts")
async def list_alerts(
    workspace_id: str,
    request: Request,
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """List workspace alert episodes with unread count (viewer+).

    Each alert includes a `detail` object (JSON). Common keys by `kind`:

    - `governance.tripped`: `code`, `decision_id`, `item_id`, `proposal_id`,
      `shacl_violation_count`, `episode_key`
    - `processing.failed`: `job_id`, `error_code`, `message`, `episode_key`
    - `sync_failed`: `source_id`, `source_name`, `mode`, `error`, `episode_key`
    `episode_key` correlates multiple rows in the UI (F-ALT).
    """
    get_workspace_for_viewer(request, user, workspace_id, store)
    alerts = knowledge.list_alerts(workspace_id, limit=limit)
    unread = knowledge.count_workspace_unread_alerts(workspace_id)
    return {"alerts": alerts, "unread_count": unread}


@router.post("/{workspace_id}/alerts/mark-all-read")
async def mark_all_alerts_read(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Mark all active alerts as read without dismissing (viewer+)."""
    get_workspace_for_viewer(request, user, workspace_id, store)
    marked_read_count = knowledge.mark_all_alerts_read(workspace_id)
    unread_count = knowledge.count_workspace_unread_alerts(workspace_id)
    return {"marked_read_count": marked_read_count, "unread_count": unread_count}


@router.post("/{workspace_id}/alerts/dismiss-all")
async def dismiss_all_alerts(
    workspace_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Dismiss all active alert episodes for this workspace (editor+)."""
    get_workspace_for_editor(request, user, workspace_id, store)
    dismissed_count = knowledge.dismiss_all_alerts(workspace_id)
    unread_count = knowledge.count_workspace_unread_alerts(workspace_id)
    return {"dismissed_count": dismissed_count, "unread_count": unread_count}


@router.post("/{workspace_id}/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    workspace_id: str,
    alert_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> dict[str, Any]:
    """Dismiss a single alert episode (editor+)."""
    get_workspace_for_editor(request, user, workspace_id, store)
    alert = knowledge.dismiss_workspace_alert(workspace_id, alert_id)
    return {"alert": alert}


@router.get("/{workspace_id}/alerts/stream")
async def stream_alerts(
    workspace_id: str,
    request: Request,
    since: str | None = Query(
        None,
        description="Only emit alerts with created_at strictly after this ISO timestamp.",
    ),
    user: User = Depends(get_current_user),
    store: AdminStore = Depends(get_store),
    knowledge: KnowledgeStore = Depends(get_knowledge_store),
) -> StreamingResponse:
    """Stream new alert episodes via SSE (viewer+)."""
    get_workspace_for_viewer(request, user, workspace_id, store)

    async def event_stream():
        cursor: str | None = since
        yield f"data: {json.dumps({'type': 'ready', 'workspace_id': workspace_id})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            alerts = await asyncio.to_thread(
                knowledge.list_alerts_since,
                workspace_id,
                since_created_at=cursor,
                limit=20,
            )
            for alert in alerts:
                cursor = alert["created_at"]
                yield f"data: {json.dumps({'type': 'alert', 'alert': alert}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
