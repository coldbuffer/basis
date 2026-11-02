"""Extraction drop audit rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

import json
from typing import Any


def insert_extraction_drop(
    conn: Any,
    *,
    drop_id: str,
    workspace_id: str,
    version_id: str,
    chunk_id: str | None,
    code: str,
    severity: str,
    detail_json: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO extraction_drops(
            id, workspace_id, version_id, chunk_id, code, severity, detail_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (drop_id, workspace_id, version_id, chunk_id, code, severity, detail_json, created_at),
    )
