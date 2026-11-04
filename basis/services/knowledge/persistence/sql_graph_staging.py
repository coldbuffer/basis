"""Graph staging session rows on the canonical workspace database."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from basis.services.knowledge.persistence.locked_conn import LockedCanonicalConn


def _staging_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphStagingPersistence:
    def __init__(self, db: LockedCanonicalConn) -> None:
        self._db = db

    def ensure_table(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_graph_staging_sessions (
                workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                session_key TEXT NOT NULL,
                from_time TEXT NOT NULL,
                to_time TEXT NOT NULL,
                draft_json TEXT NOT NULL DEFAULT '{}',
                manifest_json TEXT NOT NULL DEFAULT '{}',
                updated_by TEXT REFERENCES users(id),
                updated_at TEXT NOT NULL,
                PRIMARY KEY (workspace_id, session_key)
            )
            """
        )

    def get_draft(self, workspace_id: str, session_key: str) -> dict[str, Any] | None:
        self.ensure_table()
        row = self._db.execute(
            """
            SELECT draft_json FROM workspace_graph_staging_sessions
            WHERE workspace_id = ? AND session_key = ?
            """,
            (workspace_id, session_key),
        ).fetchone()
        if not row or not row[0]:
            return None
        try:
            parsed = json.loads(row[0])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    def upsert_session(
        self,
        workspace_id: str,
        *,
        session_key: str,
        from_time: str = "",
        to_time: str = "",
        draft: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_table()
        now = _staging_now_iso()
        existing = self._db.execute(
            """
            SELECT from_time, to_time, draft_json, manifest_json
            FROM workspace_graph_staging_sessions
            WHERE workspace_id = ? AND session_key = ?
            """,
            (workspace_id, session_key),
        ).fetchone()
        final_from = from_time or (existing[0] if existing else "")
        final_to = to_time or (existing[1] if existing else "")
        if draft is not None:
            final_draft = draft
        elif existing and existing[2]:
            try:
                final_draft = json.loads(existing[2])
            except json.JSONDecodeError:
                final_draft = {"primary": "", "duplicate": ""}
        else:
            final_draft = {"primary": "", "duplicate": ""}

        if manifest is not None:
            final_manifest = manifest
        elif existing and existing[3]:
            try:
                final_manifest = json.loads(existing[3])
            except json.JSONDecodeError:
                final_manifest = {}
        else:
            final_manifest = {}

        self._db.execute(
            """
            INSERT INTO workspace_graph_staging_sessions (
                workspace_id, session_key, from_time, to_time, draft_json, manifest_json, updated_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace_id, session_key) DO UPDATE SET
                from_time = excluded.from_time,
                to_time = excluded.to_time,
                draft_json = excluded.draft_json,
                manifest_json = excluded.manifest_json,
                updated_by = COALESCE(excluded.updated_by, workspace_graph_staging_sessions.updated_by),
                updated_at = excluded.updated_at
            """,
            (
                workspace_id,
                session_key,
                final_from,
                final_to,
                json.dumps(final_draft, ensure_ascii=False),
                json.dumps(final_manifest, ensure_ascii=False),
                updated_by,
                now,
            ),
        )
        self._db.commit()
        return {
            "workspace_id": workspace_id,
            "session_key": session_key,
            "from_time": final_from,
            "to_time": final_to,
            "draft": final_draft,
            "updated_at": now,
        }
