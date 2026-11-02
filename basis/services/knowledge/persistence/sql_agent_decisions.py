"""Agent decision audit rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

from typing import Any


def insert_agent_decision(
    conn: Any,
    *,
    decision_id: str,
    workspace_id: str,
    review_item_id: str | None,
    action: str,
    status: str,
    confidence: float,
    rationale: str | None,
    trace_json: str,
    created_at: str,
    applied_at: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO agent_decisions (
            id, workspace_id, review_item_id, action, status, confidence,
            rationale, trace_json, created_at, applied_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            decision_id,
            workspace_id,
            review_item_id,
            action,
            status,
            confidence,
            rationale,
            trace_json,
            created_at,
            applied_at,
        ),
    )
