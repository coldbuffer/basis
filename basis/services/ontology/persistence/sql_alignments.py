"""SQL persistence for published vocabulary alignments (L1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_alignment(row: Any) -> dict[str, Any]:
    return {
        "id": row["alignment_id"],
        "source_uri": row["source_uri"],
        "target_uri": row["target_uri"],
        "relation": row["relation"],
        "source_label": row["source_label"],
        "target_label": row["target_label"],
        "confidence": float(row["confidence"]),
        "provenance": row["provenance"],
        "source": row["source"],
        "reviewer": row["reviewer"],
    }


def fetch_alignments_dict(conn: Any, workspace_id: str) -> dict[str, dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT * FROM vocabulary_alignments
            WHERE workspace_id = ?
            ORDER BY alignment_id ASC
            """,
            (workspace_id,),
        ).fetchall()
    except Exception:
        return {}
    return {str(row["alignment_id"]): _row_to_alignment(row) for row in rows}


def replace_workspace_alignments(
    conn: Any,
    workspace_id: str,
    alignments: dict[str, Any],
    *,
    now: str | None = None,
) -> None:
    stamp = now or _now()
    conn.execute("DELETE FROM vocabulary_alignments WHERE workspace_id = ?", (workspace_id,))
    for alignment_id, item in alignments.items():
        if not isinstance(item, dict):
            continue
        conn.execute(
            """
            INSERT INTO vocabulary_alignments (
                workspace_id, alignment_id, source_uri, target_uri, relation,
                source_label, target_label, confidence, provenance, source, reviewer,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                str(item.get("id") or alignment_id),
                str(item.get("source_uri") or ""),
                str(item.get("target_uri") or ""),
                str(item.get("relation") or ""),
                item.get("source_label"),
                item.get("target_label"),
                float(item.get("confidence", 1.0)),
                item.get("provenance"),
                item.get("source"),
                item.get("reviewer"),
                stamp,
                stamp,
            ),
        )


def backfill_from_sidecar_dict(
    conn: Any,
    workspace_id: str,
    alignments: dict[str, Any],
) -> int:
    """Insert sidecar alignments when SQL table is empty for the workspace."""
    if not alignments:
        return 0
    existing = fetch_alignments_dict(conn, workspace_id)
    if existing:
        return 0
    replace_workspace_alignments(conn, workspace_id, alignments)
    return len(alignments)
