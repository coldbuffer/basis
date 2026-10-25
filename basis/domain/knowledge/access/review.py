"""Human review queue — KnowledgeStore API."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError

from basis.domain.errors import AdminError
from basis.domain.knowledge.persistence import sql_review_items as review_persist

if TYPE_CHECKING:
    from basis.domain.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_review_subject_key(primary_id: str, duplicate_ids: list[str]) -> str:
    parts = sorted({primary_id, *duplicate_ids})
    return ":".join(parts)


class ReviewAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def create_review_item(
        self,
        workspace_id: str,
        *,
        kind: str,
        subject_type: str,
        subject_id: str,
        payload: dict[str, Any],
        priority: int = 0,
    ) -> dict[str, Any]:
        item_id = str(uuid.uuid4())
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            try:
                review_persist.insert_review_item(
                    self._store._conn,
                    item_id=item_id,
                    workspace_id=workspace_id,
                    kind=kind,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    priority=priority,
                    payload_json=json.dumps(payload),
                    created_at=now,
                )
                self._store._conn.commit()
            except (sqlite3.IntegrityError, SQLAlchemyIntegrityError) as exc:
                raise AdminError(
                    409,
                    "review_exists",
                    "已有未处理的同类审核项",
                ) from exc
        return self.get_review_item(workspace_id, item_id)

    def count_review_items(
        self,
        workspace_id: str,
        *,
        status: str | None = "open",
        kind: str | None = None,
    ) -> int:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return review_persist.count_review_item_rows(
                self._store._conn,
                workspace_id,
                status=status,
                kind=kind,
            )

    def list_review_items(
        self,
        workspace_id: str,
        *,
        status: str | None = "open",
        kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 200)
        offset = max(0, offset)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = review_persist.list_review_item_rows(
                self._store._conn,
                workspace_id,
                status=status,
                kind=kind,
                limit=limit,
                offset=offset,
            )
        return [review_persist.review_row_to_dict(row) for row in rows]

    def find_open_review_item(
        self,
        workspace_id: str,
        *,
        kind: str,
        subject_type: str,
        subject_id: str,
    ) -> dict[str, Any] | None:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            row = review_persist.fetch_open_review_item(
                self._store._conn,
                workspace_id,
                kind=kind,
                subject_type=subject_type,
                subject_id=subject_id,
            )
        if row is None:
            return None
        return review_persist.review_row_to_dict(row)

    def get_review_item(self, workspace_id: str, item_id: str) -> dict[str, Any]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            row = review_persist.fetch_review_item(self._store._conn, workspace_id, item_id)
        if row is None:
            raise AdminError(404, "not_found", "审核项不存在")
        return review_persist.review_row_to_dict(row)

    def resolve_review_item(
        self,
        workspace_id: str,
        item_id: str,
        *,
        status: str,
        resolved_by: str,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"approved", "rejected", "cancelled"}:
            raise AdminError(422, "bad_status", "无效的审核状态")
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            row = review_persist.fetch_review_item_status(
                self._store._conn, workspace_id, item_id
            )
            if row is None:
                raise AdminError(404, "not_found", "审核项不存在")
            if row["status"] != "open":
                raise AdminError(409, "review_closed", "审核项已处理")
            review_persist.resolve_review_item_row(
                self._store._conn,
                workspace_id,
                item_id,
                status=status,
                resolved_at=now,
                resolved_by=resolved_by,
                rationale=rationale,
            )
            self._store._conn.commit()
        return self.get_review_item(workspace_id, item_id)
