"""Typed and derived facts — KnowledgeStore API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.domain.errors import AdminError
from basis.domain.knowledge.persistence import sql_derived_facts as derived_persist
from basis.domain.knowledge.persistence import sql_typed_facts as typed_persist

if TYPE_CHECKING:
    from basis.domain.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FactsAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def list_typed_facts(self, workspace_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 200)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return typed_persist.list_typed_facts_limited(
                self._store._conn, workspace_id, limit
            )

    def list_typed_facts_for_subject(
        self,
        workspace_id: str,
        subject_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 100)
        subject = str(subject_id or "").strip()
        if not subject:
            return []
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return typed_persist.list_typed_facts_for_subject(
                self._store._conn, workspace_id, subject, limit=limit
            )

    def insert_derived_fact(
        self,
        workspace_id: str,
        *,
        subject_id: str,
        predicate_uri: str,
        object_entity_id: str | None,
        object_value: str | None,
        rule_id: str | None,
        derivations: list[tuple[str, str]],
    ) -> str | None:
        if object_entity_id and object_value:
            raise AdminError(422, "validation_error", "派生事实 object 只能二选一")
        if not object_entity_id and not object_value:
            raise AdminError(422, "validation_error", "派生事实缺少 object")
        now = _now()
        with self._store._lock:
            conn = self._store._conn
            self._store._assert_row_in_workspace("entities", subject_id, workspace_id)
            if object_entity_id:
                self._store._assert_row_in_workspace("entities", object_entity_id, workspace_id)
            if derived_persist.find_active_derived_fact_duplicate(
                conn,
                workspace_id,
                subject_id,
                predicate_uri,
                object_entity_id,
                object_value,
            ):
                return None
            fact_id = str(uuid.uuid4())
            derived_persist.insert_derived_fact_row(
                conn,
                fact_id=fact_id,
                workspace_id=workspace_id,
                subject_id=subject_id,
                predicate_uri=predicate_uri,
                object_entity_id=object_entity_id,
                object_value=object_value,
                rule_id=rule_id,
                recorded_at=now,
            )
            for ordinal, (premise_kind, premise_id) in enumerate(derivations):
                derived_persist.insert_fact_derivation(
                    conn, fact_id, premise_kind, premise_id, ordinal
                )
            conn.commit()
        return fact_id

    def list_derived_facts(self, workspace_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 200)
        with self._store._lock:
            return derived_persist.list_derived_facts_limited(
                self._store._conn, workspace_id, limit
            )

    def list_derived_facts_for_entity(
        self,
        workspace_id: str,
        entity_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 100)
        with self._store._lock:
            self._store._assert_row_in_workspace("entities", entity_id, workspace_id)
            return derived_persist.list_derived_facts_for_entity(
                self._store._conn, workspace_id, entity_id, limit
            )
