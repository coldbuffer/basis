"""Audit log reads and external record hook."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from basis.services.tenancy.admin.persistence import audit as audit_persist

if TYPE_CHECKING:
    from basis.services.tenancy.admin.store import AdminStore


class AuditAccess:
    def __init__(self, store: AdminStore) -> None:
        self._store = store

    def list_audit(
        self,
        limit: int = 100,
        *,
        action_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 200)
        with self._store._lock:
            rows = audit_persist.list_audit(
                self._store._conn, limit, action_prefix=action_prefix
            )
        return [audit_persist.audit_row_to_dict(row) for row in rows]

    def list_audit_for_workspace(
        self,
        workspace_id: str,
        *,
        action_prefix: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 200)
        with self._store._lock:
            rows = audit_persist.list_audit_for_workspace(
                self._store._conn,
                workspace_id,
                limit,
                action_prefix=action_prefix,
                backend=self._store._db.backend,
            )
        return [audit_persist.audit_row_to_dict(row) for row in rows]

    def record_audit(
        self,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        payload = dict(detail or {})
        from basis.infra.observability.request_context import current_request_id

        rid = current_request_id()
        if rid and "request_id" not in payload:
            payload["request_id"] = rid
        with self._store._lock:
            audit_persist.insert_audit(
                self._store._conn,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                detail=payload,
            )
            self._store._conn.commit()
