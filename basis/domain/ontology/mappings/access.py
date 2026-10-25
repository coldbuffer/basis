"""Ontology surface → URI mappings — KnowledgeStore API."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError

from basis.domain.errors import AdminError
from basis.domain.ontology.mappings import sql as mapping_persist
from basis.domain.ontology.mappings.entity_type import (
    entity_type_surface_phrases_from_config,
    filter_type_phrases,
    object_label_from_statement_row,
    statement_matches_object_label,
)

if TYPE_CHECKING:
    from basis.domain.knowledge.store import KnowledgeStore

MAPPING_TARGET_KINDS = frozenset({"class", "property", "none"})
MAPPING_DIRECTIONS = frozenset({"forward", "reverse", "n/a"})
MAPPING_STATUSES = frozenset({"proposed", "confirmed", "rejected", "superseded"})
RDF_TYPE_URI = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MappingsAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def list_mappings(
        self,
        workspace_id: str,
        *,
        status: str | None = None,
        include_invalidated: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = min(max(1, limit), 200)
        if status and status not in MAPPING_STATUSES:
            raise AdminError(422, "bad_status", "无效的映射状态")
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = mapping_persist.list_mapping_rows(
                self._store._conn,
                workspace_id,
                include_invalidated=include_invalidated,
                status=status,
                limit=limit,
            )
        return [mapping_persist.mapping_row_to_dict(row) for row in rows]

    def create_mapping(
        self,
        workspace_id: str,
        actor_id: str,
        *,
        signature: str,
        target_uri: str | None,
        target_kind: str,
        direction: str,
        status: str = "proposed",
        why: str | None = None,
    ) -> dict[str, Any]:
        signature = signature.strip()
        if not signature:
            raise AdminError(422, "bad_signature", "映射签名不能为空")
        if target_kind not in MAPPING_TARGET_KINDS:
            raise AdminError(422, "bad_target_kind", "target_kind 无效")
        if direction not in MAPPING_DIRECTIONS:
            raise AdminError(422, "bad_direction", "direction 无效")
        if status not in MAPPING_STATUSES:
            raise AdminError(422, "bad_status", "status 无效")
        mapping_id = str(uuid.uuid4())
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            try:
                mapping_persist.insert_mapping(
                    self._store._conn,
                    mapping_id=mapping_id,
                    workspace_id=workspace_id,
                    signature=signature,
                    target_uri=target_uri,
                    target_kind=target_kind,
                    direction=direction,
                    status=status,
                    actor_id=actor_id,
                    why=why,
                    created_at=now,
                )
                self._store._conn.commit()
            except (sqlite3.IntegrityError, SQLAlchemyIntegrityError) as exc:
                raise AdminError(
                    409,
                    "mapping_exists",
                    "已存在相同签名的已确认映射",
                ) from exc
        return self.get_mapping(workspace_id, mapping_id)

    def get_mapping(self, workspace_id: str, mapping_id: str) -> dict[str, Any]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            row = mapping_persist.fetch_mapping(
                self._store._conn, workspace_id, mapping_id
            )
        if row is None:
            raise AdminError(404, "not_found", "映射不存在")
        return mapping_persist.mapping_row_to_dict(row)

    def update_mapping_status(
        self,
        workspace_id: str,
        mapping_id: str,
        actor_id: str,
        *,
        status: str,
        why: str | None = None,
    ) -> dict[str, Any]:
        if status not in MAPPING_STATUSES:
            raise AdminError(422, "bad_status", "status 无效")
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            row = mapping_persist.fetch_mapping_status_row(
                self._store._conn, workspace_id, mapping_id
            )
            if row is None:
                raise AdminError(404, "not_found", "映射不存在")
            if row["invalidated_at"] is not None:
                raise AdminError(409, "mapping_invalidated", "映射已失效")
            try:
                mapping_persist.update_mapping_status_row(
                    self._store._conn,
                    workspace_id,
                    mapping_id,
                    status=status,
                    why=why,
                    actor_id=actor_id,
                )
                if status in {"rejected", "superseded"}:
                    mapping_persist.invalidate_mapping_row(
                        self._store._conn, workspace_id, mapping_id, now
                    )
                self._store._conn.commit()
            except (sqlite3.IntegrityError, SQLAlchemyIntegrityError) as exc:
                raise AdminError(
                    409, "mapping_exists", "已存在相同签名的已确认映射"
                ) from exc
        return self.get_mapping(workspace_id, mapping_id)

    def list_distinct_surface_phrases(self, workspace_id: str, *, limit: int = 100) -> list[str]:
        limit = min(max(1, limit), 200)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            return mapping_persist.list_distinct_surface_phrases(
                self._store._conn, workspace_id, limit
            )

    def entity_type_surface_phrases(self, workspace_id: str) -> list[str]:
        config = self._store.get_governance_config(workspace_id)
        return filter_type_phrases(entity_type_surface_phrases_from_config(config))

    def _entity_type_surface_phrases(self, workspace_id: str) -> list[str]:
        return self.entity_type_surface_phrases(workspace_id)

    def list_entity_type_object_labels(self, workspace_id: str, *, limit: int = 100) -> list[str]:
        limit = min(max(1, limit), 200)
        type_phrases = self._entity_type_surface_phrases(workspace_id)
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = mapping_persist.statements_for_entity_type_materialization(
                self._store._conn, workspace_id, type_phrases
            )
        labels: list[str] = []
        seen: set[str] = set()
        for row in rows:
            label = object_label_from_statement_row(row)
            if not label:
                continue
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            labels.append(label)
            if len(labels) >= limit:
                break
        return sorted(labels, key=lambda s: s.casefold())

    def materialize_mapping_facts(self, workspace_id: str, mapping_id: str) -> dict[str, Any]:
        mapping = self.get_mapping(workspace_id, mapping_id)
        if mapping["status"] != "confirmed":
            return {"created": 0, "reason": "mapping_not_confirmed"}
        target_kind = mapping["target_kind"]
        if target_kind == "property":
            return self._materialize_property_mapping_facts(workspace_id, mapping_id, mapping)
        if target_kind == "class":
            return self._materialize_class_mapping_facts(workspace_id, mapping_id, mapping)
        return {"created": 0, "reason": "target_not_materializable", "mapping_id": mapping_id}

    def _materialize_property_mapping_facts(
        self,
        workspace_id: str,
        mapping_id: str,
        mapping: dict[str, Any],
    ) -> dict[str, Any]:
        predicate_uri = (mapping["target_uri"] or "").strip()
        if not predicate_uri:
            return {"created": 0, "reason": "missing_predicate_uri", "mapping_id": mapping_id}
        signature = mapping["signature"]
        now = _now()
        created = 0
        with self._store._lock:
            conn = self._store._conn
            rows = mapping_persist.statements_for_mapping_materialization(
                conn, workspace_id, signature
            )
            for row in rows:
                object_entity_id = row["object_entity_id"]
                object_value = row["object_value"]
                if object_entity_id and object_value:
                    continue
                if not object_entity_id and not object_value:
                    continue
                if mapping_persist.typed_fact_exists_for_statement_mapping(
                    conn, workspace_id, row["id"], mapping_id
                ):
                    continue
                fact_id = str(uuid.uuid4())
                mapping_persist.insert_typed_fact_from_statement(
                    conn,
                    fact_id=fact_id,
                    workspace_id=workspace_id,
                    subject_id=row["subject_id"],
                    predicate_uri=predicate_uri,
                    object_entity_id=object_entity_id,
                    object_value=object_value,
                    from_statement_id=row["id"],
                    mapping_id=mapping_id,
                    confidence=row["confidence"],
                    recorded_at=now,
                )
                created += 1
            conn.commit()
        return {"created": created, "mapping_id": mapping_id}

    def _materialize_class_mapping_facts(
        self,
        workspace_id: str,
        mapping_id: str,
        mapping: dict[str, Any],
    ) -> dict[str, Any]:
        class_uri = (mapping["target_uri"] or "").strip()
        if not class_uri:
            return {"created": 0, "reason": "missing_class_uri", "mapping_id": mapping_id}
        object_label = (mapping["signature"] or "").strip()
        if not object_label:
            return {"created": 0, "reason": "missing_object_label", "mapping_id": mapping_id}
        type_phrases = self._entity_type_surface_phrases(workspace_id)
        if not type_phrases:
            return {"created": 0, "reason": "no_type_surface_phrases", "mapping_id": mapping_id}
        now = _now()
        created = 0
        with self._store._lock:
            conn = self._store._conn
            rows = mapping_persist.statements_for_entity_type_materialization(
                conn, workspace_id, type_phrases
            )
            for row in rows:
                if not statement_matches_object_label(row, object_label):
                    continue
                subject_id = row["subject_id"]
                if not subject_id:
                    continue
                if mapping_persist.typed_fact_exists_for_statement_mapping(
                    conn, workspace_id, row["id"], mapping_id
                ):
                    continue
                fact_id = str(uuid.uuid4())
                mapping_persist.insert_typed_fact_from_statement(
                    conn,
                    fact_id=fact_id,
                    workspace_id=workspace_id,
                    subject_id=subject_id,
                    predicate_uri=RDF_TYPE_URI,
                    object_entity_id=None,
                    object_value=class_uri,
                    from_statement_id=row["id"],
                    mapping_id=mapping_id,
                    confidence=row["confidence"],
                    recorded_at=now,
                )
                created += 1
            conn.commit()
        return {"created": created, "mapping_id": mapping_id}
