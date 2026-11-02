"""Graph diff staging manifest (F-DIFF-01 read path + governance hints)."""

from __future__ import annotations

import hashlib
from typing import Any

from basis.services.graph.reads.diff import diff_session_at


def staging_session_key(workspace_id: str, from_time: str, to_time: str) -> str:
    """Stable id for a compare range (client draft persistence; F-DIFF-01)."""
    payload = f"{workspace_id}\x1f{from_time.strip()}\x1f{to_time.strip()}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def _change_total(summary: dict[str, Any]) -> int:
    return sum(int(summary.get(key) or 0) for key in (
        "nodes_added",
        "nodes_removed",
        "nodes_modified",
        "edges_added",
        "edges_removed",
    ))


def build_graph_staging_payload(
    workspace_id: str,
    diff: dict[str, Any],
    *,
    draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = dict(diff.get("summary") or {})
    focus_node_ids: list[str] = list(diff.get("added_nodes") or [])
    focus_node_ids.extend(row["id"] for row in diff.get("modified_nodes") or [] if row.get("id"))
    from_time = str(diff.get("from_time") or "")
    to_time = str(diff.get("to_time") or "")
    return {
        "workspace_id": workspace_id,
        "manifest": {
            "session_key": staging_session_key(workspace_id, from_time, to_time),
            "from_time": from_time or diff.get("from_time"),
            "to_time": to_time or diff.get("to_time"),
            "change_total": _change_total(summary),
            "summary": summary,
            "focus_node_ids": focus_node_ids,
            "removed_node_ids": list(diff.get("removed_nodes") or []),
            "draft": draft or {"primary": "", "duplicate": ""},
            "governance": {
                "direct_merge_allowed": False,
                "review_queue_relpath": "review",
                "entity_merge_proposal_relpath": "graph/staging/entity-merge",
                "graph_import_relpath": "review/items/graph-import",
            },
        },
        "diff": diff,
    }


def graph_staging_at(
    session: Any,
    workspace_id: str,
    from_time: str,
    to_time: str,
    *,
    conn: Any = None,
    updated_by: str | None = None,
) -> dict[str, Any]:
    """Diff-only staging payload (no DB). Use KnowledgeStore.graph_staging_at to persist."""
    diff = diff_session_at(session, from_time, to_time)
    return build_graph_staging_payload(workspace_id, diff)
