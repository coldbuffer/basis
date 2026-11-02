"""One org per existing workspace; attach workspace owners as org owners."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

ORG_ROLES = frozenset({"owner", "admin", "member"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_for_workspace(workspace_id: str, name: str) -> str:
    base = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")
    base = base[:48] or "workspace"
    return f"{base}-{workspace_id[:8]}"


def _backfill_pending_workspaces(conn: Any, *, commit: bool) -> int:
    pending = conn.execute(
        """
        SELECT id, name, created_by FROM workspaces
        WHERE organization_id IS NULL OR TRIM(organization_id) = ''
        """
    ).fetchall()
    count = 0
    for row in pending:
        workspace_id = row["id"]
        org_id = str(uuid.uuid4())
        slug = _slug_for_workspace(workspace_id, row["name"] or "org")
        while conn.execute("SELECT 1 FROM organizations WHERE slug = ?", (slug,)).fetchone():
            slug = f"{slug}-{org_id[:6]}"
        conn.execute(
            """
            INSERT INTO organizations(id, name, slug, auth_policy, created_at)
            VALUES (?, ?, ?, 'password_allowed', ?)
            """,
            (org_id, row["name"] or "Organization", slug, _now()),
        )
        owner_id = row["created_by"]
        owners = conn.execute(
            """
            SELECT user_id FROM members
            WHERE workspace_id = ? AND role = 'owner'
            """,
            (workspace_id,),
        ).fetchall()
        member_ids = {owner_id}
        for o in owners:
            member_ids.add(o["user_id"])
        for uid in member_ids:
            if not uid:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO org_members(organization_id, user_id, role, joined_at)
                VALUES (?, ?, 'owner', ?)
                """,
                (org_id, uid, _now()),
            )
        conn.execute(
            "UPDATE workspaces SET organization_id = ? WHERE id = ?",
            (org_id, workspace_id),
        )
        count += 1
    if count and commit:
        conn.commit()
    return count


def ensure_organization_backfill(conn: sqlite3.Connection) -> int:
    """Idempotent. Returns count of workspaces backfilled (SQLite admin DB)."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='organizations'"
    ).fetchone()
    if row is None:
        return 0
    workspace_cols = {r[1] for r in conn.execute("PRAGMA table_info(workspaces)").fetchall()}
    if "organization_id" not in workspace_cols:
        return 0
    return _backfill_pending_workspaces(conn, commit=True)


def ensure_organization_backfill_postgres(conn: Any) -> int:
    """Idempotent backfill when migration runs inside a SQLAlchemy transaction."""
    from sqlalchemy import text

    exists = conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'organizations'
            )
            """
        )
    ).scalar()
    if not exists:
        return 0
    has_col = conn.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'workspaces'
                  AND column_name = 'organization_id'
            )
            """
        )
    ).scalar()
    if not has_col:
        return 0

    class _PgCompat:
        def execute(self, sql: str, params=()):
            stmt = sql.replace("?", "%s")
            if "INSERT OR IGNORE INTO org_members" in sql:
                stmt = """
                    INSERT INTO org_members(organization_id, user_id, role, joined_at)
                    VALUES (%s, %s, 'owner', %s)
                    ON CONFLICT (organization_id, user_id) DO NOTHING
                """
            else:
                stmt = stmt.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            result = conn.exec_driver_sql(stmt, params)
            return _PgResult(result)

    return _backfill_pending_workspaces(_PgCompat(), commit=False)


class _PgResult:
    def __init__(self, result) -> None:
        self._result = result

    def fetchone(self):
        row = self._result.fetchone()
        if row is None:
            return None
        keys = list(self._result.keys())
        return {k: row[i] for i, k in enumerate(keys)}

    def fetchall(self):
        keys = list(self._result.keys())
        return [{k: row[i] for i, k in enumerate(keys)} for row in self._result.fetchall()]


def parse_email_domains(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(d).strip().lower() for d in data if str(d).strip()]
