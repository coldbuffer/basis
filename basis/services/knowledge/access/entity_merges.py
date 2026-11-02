"""Entity merges, agent decisions, and entity lookups — KnowledgeStore API."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.services.errors import AdminError
from basis.services.knowledge.persistence import sql_agent_decisions as decision_persist
from basis.services.knowledge.persistence import sql_entities as entity_persist
from basis.services.knowledge.persistence import sql_entity_merges as merge_persist

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EntityMergesAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def entity_labels_by_ids(
        self, workspace_id: str, entity_ids: list[str]
    ) -> dict[str, str | None]:
        with self._store._lock:
            return entity_persist.entity_labels_by_ids(
                self._store._conn, workspace_id, entity_ids
            )

    def ledger_entity_exists(self, workspace_id: str, entity_id: str) -> bool:
        with self._store._lock:
            return entity_persist.active_entity_exists(
                self._store._conn, workspace_id, entity_id
            )

    def record_agent_decision(
        self,
        workspace_id: str,
        *,
        action: str,
        review_item_id: str | None = None,
        rationale: str | None = None,
        trace: dict[str, Any] | None = None,
        status: str = "applied",
        confidence: float = 1.0,
        decision_id: str | None = None,
    ) -> str:
        resolved_id = decision_id or f"dec_{uuid.uuid4().hex[:16]}"
        now = _now()
        with self._store._lock:
            decision_persist.insert_agent_decision(
                self._store._conn,
                decision_id=resolved_id,
                workspace_id=workspace_id,
                review_item_id=review_item_id,
                action=action,
                status=status,
                confidence=confidence,
                rationale=rationale,
                trace_json=json.dumps(trace or {}, default=str),
                created_at=now,
                applied_at=now if status == "applied" else None,
            )
            self._store._conn.commit()
        return resolved_id

    def record_entity_merge(
        self,
        workspace_id: str,
        *,
        source_entity_id: str,
        target_entity_id: str,
        actor_id: str | None,
        why: str | None = None,
        decision_id: str | None = None,
    ) -> dict[str, Any]:
        if source_entity_id == target_entity_id:
            raise AdminError(422, "same_entity", "不能合并同一实体")
        with self._store._lock:
            self._store._assert_row_in_workspace("entities", source_entity_id, workspace_id)
            self._store._assert_row_in_workspace("entities", target_entity_id, workspace_id)
            merge_id = str(uuid.uuid4())
            now = _now()
            merge_persist.insert_entity_merge(
                self._store._conn,
                merge_id=merge_id,
                workspace_id=workspace_id,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                decision_id=decision_id,
                actor_id=actor_id,
                why=why,
                created_at=now,
            )
            self._store._conn.commit()
            row = merge_persist.fetch_entity_merge_by_id(self._store._conn, merge_id)
        return merge_persist.entity_merge_row_to_dict(row)

    def entity_merge_redirect(self, workspace_id: str) -> dict[str, str]:
        direct: dict[str, str] = {}
        for row in self.list_entity_merges(workspace_id, active_only=True, limit=10_000):
            direct[row["source_entity_id"]] = row["target_entity_id"]
        redirect: dict[str, str] = {}
        for source in direct:
            target = direct[source]
            seen = {source}
            while target in direct and target not in seen:
                seen.add(target)
                target = direct[target]
            redirect[source] = target
        return redirect

    def revert_entity_merge(
        self,
        workspace_id: str,
        merge_id: str,
        *,
        reverted_by: str,
    ) -> dict[str, Any]:
        with self._store._lock:
            row = merge_persist.fetch_entity_merge_for_workspace(
                self._store._conn, merge_id, workspace_id
            )
            if row is None:
                raise AdminError(404, "not_found", "合并记录不存在")
            if row["reverted_at"] is not None:
                raise AdminError(409, "merge_reverted", "合并已回滚")
            now = _now()
            merge_persist.revert_entity_merge_row(
                self._store._conn,
                merge_id,
                workspace_id,
                reverted_at=now,
                reverted_by=reverted_by,
            )
            self._store._conn.commit()
            updated = merge_persist.fetch_entity_merge_by_id(
                self._store._conn, merge_id
            )
        return merge_persist.entity_merge_row_to_dict(updated)

    def list_entity_merges(
        self,
        workspace_id: str,
        *,
        limit: int = 100,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = merge_persist.list_entity_merge_rows(
                self._store._conn,
                workspace_id,
                active_only=active_only,
                limit=limit,
            )
        return [merge_persist.entity_merge_row_to_dict(row) for row in rows]
