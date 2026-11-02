"""Workspace alerts — KnowledgeStore API."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.services.errors import AdminError
from basis.services.knowledge.persistence import sql_alerts as alert_persist

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkspaceAlertsAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def create_workspace_alert(
        self,
        workspace_id: str,
        *,
        kind: str,
        message: str,
        severity: str = "warning",
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        alert_id = str(uuid.uuid4())
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            alert_persist.insert_workspace_alert(
                self._store._conn,
                alert_id=alert_id,
                workspace_id=workspace_id,
                kind=kind,
                severity=severity,
                message=message[:2000],
                detail_json=json.dumps(detail or {}, ensure_ascii=False),
                created_at=now,
            )
            self._store._conn.commit()
        return self.get_workspace_alert(workspace_id, alert_id)

    def get_workspace_alert(self, workspace_id: str, alert_id: str) -> dict[str, Any]:
        with self._store._lock:
            row = alert_persist.fetch_workspace_alert(self._store._conn, workspace_id, alert_id)
        if row is None:
            raise AdminError(404, "not_found", "告警不存在")
        return alert_persist.alert_row_to_dict(row)

    def list_alerts(
        self,
        workspace_id: str,
        *,
        include_dismissed: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 100)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = alert_persist.list_workspace_alert_rows(
                self._store._conn,
                workspace_id,
                include_dismissed=include_dismissed,
                limit=limit,
            )
        return [alert_persist.alert_row_to_dict(row) for row in rows]

    def count_alerts(self, workspace_id: str, *, include_dismissed: bool = False) -> int:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return alert_persist.count_alerts(
                self._store._conn, workspace_id, include_dismissed=include_dismissed
            )

    def count_workspace_unread_alerts(self, workspace_id: str) -> int:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return alert_persist.count_workspace_unread_alerts(self._store._conn, workspace_id)

    def list_alerts_since(
        self,
        workspace_id: str,
        *,
        since_created_at: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 50)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = alert_persist.list_alerts_since_rows(
                self._store._conn,
                workspace_id,
                since_created_at=since_created_at,
                limit=limit,
            )
        items = [alert_persist.alert_row_to_dict(row) for row in rows]
        if since_created_at is None:
            items.reverse()
        return items

    def dismiss_workspace_alert(self, workspace_id: str, alert_id: str) -> dict[str, Any]:
        now = _now()
        self.get_workspace_alert(workspace_id, alert_id)
        with self._store._lock:
            alert_persist.dismiss_workspace_alert_row(
                self._store._conn,
                workspace_id,
                alert_id,
                dismissed_at=now,
                read_at=now,
            )
            self._store._conn.commit()
        return self.get_workspace_alert(workspace_id, alert_id)

    def dismiss_all_alerts(self, workspace_id: str) -> int:
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            n = alert_persist.dismiss_all_alerts(
                self._store._conn, workspace_id, dismissed_at=now, read_at=now
            )
            self._store._conn.commit()
            return n

    def mark_all_alerts_read(self, workspace_id: str) -> int:
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            n = alert_persist.mark_all_alerts_read(
                self._store._conn, workspace_id, read_at=now
            )
            self._store._conn.commit()
            return n
