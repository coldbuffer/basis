"""Workspace reasoning rules — KnowledgeStore API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.services.errors import AdminError
from basis.services.ontology.persistence import sql_reasoning_rules as rule_persist

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReasoningRulesAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def list_reasoning_rules(
        self, workspace_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 200)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = rule_persist.list_reasoning_rule_rows(
                self._store._conn, workspace_id, limit
            )
        return [rule_persist.reasoning_rule_row_to_dict(row) for row in rows]

    def create_reasoning_rule(
        self,
        workspace_id: str,
        *,
        name: str,
        body: str,
        actor_id: str,
        enabled: bool = True,
    ) -> dict[str, Any]:
        rule_id = str(uuid.uuid4())
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rule_persist.insert_reasoning_rule(
                self._store._conn,
                rule_id=rule_id,
                workspace_id=workspace_id,
                name=name,
                body=body,
                enabled=int(enabled),
                actor_id=actor_id,
                created_at=now,
                updated_at=now,
            )
            self._store._conn.commit()
        return self.get_reasoning_rule(workspace_id, rule_id)

    def get_reasoning_rule(self, workspace_id: str, rule_id: str) -> dict[str, Any]:
        with self._store._lock:
            row = rule_persist.fetch_reasoning_rule(
                self._store._conn, workspace_id, rule_id
            )
        if row is None:
            raise AdminError(404, "not_found", "规则不存在")
        return rule_persist.reasoning_rule_row_to_dict(row)

    def update_reasoning_rule(
        self,
        workspace_id: str,
        rule_id: str,
        *,
        name: str | None = None,
        body: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        self.get_reasoning_rule(workspace_id, rule_id)
        if name is None and body is None and enabled is None:
            return self.get_reasoning_rule(workspace_id, rule_id)
        now = _now()
        sets: list[str] = ["updated_at = ?"]
        params: list[Any] = [now]
        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if body is not None:
            sets.append("body = ?")
            params.append(body)
        if enabled is not None:
            sets.append("enabled = ?")
            params.append(int(enabled))
        params.extend([workspace_id, rule_id])
        with self._store._lock:
            rule_persist.update_reasoning_rule_dynamic(
                self._store._conn,
                workspace_id,
                rule_id,
                ", ".join(sets),
                params,
            )
            self._store._conn.commit()
        return self.get_reasoning_rule(workspace_id, rule_id)

    def delete_reasoning_rule(self, workspace_id: str, rule_id: str) -> None:
        self.get_reasoning_rule(workspace_id, rule_id)
        now = _now()
        with self._store._lock:
            rule_persist.soft_delete_reasoning_rule(
                self._store._conn,
                workspace_id,
                rule_id,
                deleted_at=now,
                updated_at=now,
            )
            self._store._conn.commit()
