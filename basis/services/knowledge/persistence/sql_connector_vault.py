"""BOCP vault tables (policies, OAuth configs, connections, audit runs) — canonical DB SQL."""

from __future__ import annotations

import json
from typing import Any

from basis.services.knowledge.ports.connector import LockedCanonicalConn


class ConnectorVaultPersistence:
    """SQL access for connector vault tables; uses LockedCanonicalConn for locking."""

    def __init__(self, db: LockedCanonicalConn) -> None:
        self._db = db

    def fetch_policy_row(self, workspace_id: str) -> Any:
        return self._db.execute(
            """
            SELECT allowed_providers_json, action_policy_json, updated_at
            FROM connector_policies
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

    def upsert_policy(
        self,
        workspace_id: str,
        allowed_json: str,
        action_json: str,
        updated_at: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO connector_policies (workspace_id, allowed_providers_json, action_policy_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET
                allowed_providers_json = excluded.allowed_providers_json,
                action_policy_json = excluded.action_policy_json,
                updated_at = excluded.updated_at
            """,
            (workspace_id, allowed_json, action_json, updated_at),
        )
        self._db.commit()

    def fetch_oauth_config_row(self, workspace_id: str, service: str) -> Any:
        return self._db.execute(
            "SELECT value_encrypted, updated_at FROM connector_oauth_configs WHERE workspace_id = ? AND service = ?",
            (workspace_id, service),
        ).fetchone()

    def upsert_oauth_config(
        self,
        workspace_id: str,
        service: str,
        value_encrypted: str,
        updated_at: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO connector_oauth_configs (workspace_id, service, value_encrypted, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(workspace_id, service) DO UPDATE SET
                value_encrypted = excluded.value_encrypted,
                updated_at = excluded.updated_at
            """,
            (workspace_id, service, value_encrypted, updated_at),
        )
        self._db.commit()

    def fetch_connection_row(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: str = "workspace",
        subject_id: str = "",
    ) -> Any:
        return self._db.execute(
            """
            SELECT auth_type, connection_config_json, value_encrypted,
                   account_profile_json, revision, updated_at,
                   connection_scope, subject_id
            FROM connector_connections
            WHERE workspace_id = ? AND service = ?
              AND connection_scope = ? AND subject_id = ?
            """,
            (workspace_id, service, connection_scope, subject_id),
        ).fetchone()

    def list_connection_rows(
        self,
        workspace_id: str,
        *,
        service: str | None = None,
        connection_scope: str | None = None,
        subject_id: str | None = None,
    ) -> list[Any]:
        clauses = ["workspace_id = ?"]
        params: list[Any] = [workspace_id]
        if service:
            clauses.append("service = ?")
            params.append(service)
        if connection_scope is not None:
            clauses.append("connection_scope = ?")
            params.append(connection_scope)
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        where = " AND ".join(clauses)
        return self._db.execute(
            f"""
            SELECT service, auth_type, connection_config_json,
                   value_encrypted, account_profile_json, revision, updated_at,
                   connection_scope, subject_id
            FROM connector_connections
            WHERE {where}
            ORDER BY service, connection_scope, subject_id
            """,
            tuple(params),
        ).fetchall()

    def upsert_connection(
        self,
        *,
        workspace_id: str,
        service: str,
        connection_scope: str,
        subject_id: str,
        auth_type: str,
        connection_config_json: str,
        value_encrypted: str,
        account_profile_json: str,
        revision: int,
        updated_at: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO connector_connections (
                workspace_id, service, connection_scope, subject_id,
                auth_type, connection_config_json, value_encrypted, account_profile_json,
                revision, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace_id, service, connection_scope, subject_id) DO UPDATE SET
                auth_type = excluded.auth_type,
                connection_config_json = excluded.connection_config_json,
                value_encrypted = excluded.value_encrypted,
                account_profile_json = excluded.account_profile_json,
                revision = excluded.revision,
                updated_at = excluded.updated_at
            """,
            (
                workspace_id,
                service,
                connection_scope,
                subject_id,
                auth_type,
                connection_config_json,
                value_encrypted,
                account_profile_json,
                revision,
                updated_at,
            ),
        )
        self._db.commit()

    def delete_connection(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: str = "workspace",
        subject_id: str = "",
    ) -> int:
        cur = self._db.execute(
            """
            DELETE FROM connector_connections
            WHERE workspace_id = ? AND service = ?
              AND connection_scope = ? AND subject_id = ?
            """,
            (workspace_id, service, connection_scope, subject_id),
        )
        self._db.commit()
        return int(cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0)

    def insert_connector_run(
        self,
        *,
        run_id: str,
        workspace_id: str,
        service: str,
        operation_kind: str,
        target_id: str,
        started_at: str,
        completed_at: str,
        ok: int,
        value_json: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO connector_runs (
                id, workspace_id, service, operation_kind, target_id,
                started_at, completed_at, ok, value_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                workspace_id,
                service,
                operation_kind,
                target_id,
                started_at,
                completed_at,
                ok,
                value_json,
            ),
        )
        self._db.commit()

    def list_connector_runs(
        self,
        workspace_id: str,
        *,
        service: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if service:
            rows = self._db.execute(
                """
                SELECT id, service, operation_kind, target_id,
                       started_at, completed_at, ok, value_json
                FROM connector_runs
                WHERE workspace_id = ? AND service = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (workspace_id, service, limit),
            ).fetchall()
        else:
            rows = self._db.execute(
                """
                SELECT id, service, operation_kind, target_id,
                       started_at, completed_at, ok, value_json
                FROM connector_runs
                WHERE workspace_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (workspace_id, limit),
            ).fetchall()
        runs: list[dict[str, Any]] = []
        for row in rows:
            runs.append(
                {
                    "id": row[0],
                    "service": row[1],
                    "operation_kind": row[2],
                    "target_id": row[3],
                    "started_at": row[4],
                    "completed_at": row[5],
                    "ok": bool(row[6]),
                    "value": json.loads(row[7]) if row[7] else {},
                }
            )
        return runs
