"""Entity, chunk, and statement writes used by ingest / extraction."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.domain.errors import AdminError
from basis.domain.knowledge.persistence import sql_chunks as chunk_persist
from basis.domain.knowledge.persistence import sql_entities as entity_persist
from basis.domain.knowledge.persistence import sql_extraction_drops as drop_persist
from basis.domain.knowledge.persistence import sql_statements as stmt_persist

if TYPE_CHECKING:
    from basis.domain.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestLedgerAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def get_or_create_entity_by_label(self, workspace_id: str, label: str) -> str:
        clean = label.strip()
        if not clean:
            raise AdminError(422, "bad_entity", "实体名称无效")
        with self._store._lock:
            row = entity_persist.find_active_entity_id_by_label(
                self._store._conn, workspace_id, clean
            )
        if row is not None:
            return row["id"]
        return self.create_entity(workspace_id, canonical_label=clean)

    def create_entity(
        self,
        workspace_id: str,
        *,
        canonical_label: str | None = None,
        description: str | None = None,
        entity_kind: str = "named",
    ) -> str:
        if entity_kind not in {"named", "described"}:
            raise AdminError(422, "bad_entity_kind", "实体类型无效")
        entity_id = str(uuid.uuid4())
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            entity_persist.insert_entity(
                self._store._conn,
                entity_id=entity_id,
                workspace_id=workspace_id,
                canonical_label=canonical_label,
                description=description,
                entity_kind=entity_kind,
                created_at=_now(),
            )
            self._store._conn.commit()
        return entity_id

    def count_entities_named(self, workspace_id: str, label: str) -> int:
        with self._store._lock:
            return entity_persist.count_entities_named(self._store._conn, workspace_id, label)

    def find_entity_id_by_label(self, workspace_id: str, label: str) -> str | None:
        clean = label.strip()
        if not clean:
            return None
        with self._store._lock:
            row = entity_persist.find_active_entity_id_by_label(
                self._store._conn, workspace_id, clean
            )
        return None if row is None else str(row["id"])

    def has_statement_on_chunk(
        self,
        workspace_id: str,
        chunk_id: str,
        subject_id: str,
        surface_phrase: str,
        *,
        object_entity_id: str | None,
        object_value: str | None,
    ) -> bool:
        with self._store._lock:
            return stmt_persist.has_statement_on_chunk(
                self._store._conn,
                workspace_id,
                chunk_id,
                subject_id,
                surface_phrase,
                object_entity_id=object_entity_id,
                object_value=object_value,
            )

    def has_equivalent_statement(
        self,
        workspace_id: str,
        subject_id: str,
        surface_phrase: str,
        *,
        object_entity_id: str | None,
        object_value: str | None,
    ) -> bool:
        with self._store._lock:
            return stmt_persist.has_equivalent_statement(
                self._store._conn,
                workspace_id,
                subject_id,
                surface_phrase,
                object_entity_id=object_entity_id,
                object_value=object_value,
            )

    def add_extraction_drop(
        self,
        workspace_id: str,
        version_id: str,
        chunk_id: str | None,
        code: str,
        detail: dict[str, Any],
        *,
        severity: str = "drop",
    ) -> str:
        drop_id = str(uuid.uuid4())
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            self._store._assert_row_in_workspace("document_versions", version_id, workspace_id)
            if chunk_id:
                self._store._assert_row_in_workspace("chunks", chunk_id, workspace_id)
            drop_persist.insert_extraction_drop(
                self._store._conn,
                drop_id=drop_id,
                workspace_id=workspace_id,
                version_id=version_id,
                chunk_id=chunk_id,
                code=code,
                severity=severity,
                detail_json=json.dumps(detail, ensure_ascii=False, default=str),
                created_at=_now(),
            )
            self._store._conn.commit()
        return drop_id

    def count_statements_for_version(self, workspace_id: str, version_id: str) -> int:
        with self._store._lock:
            return stmt_persist.count_statements_for_version(
                self._store._conn, workspace_id, version_id
            )

    def add_open_statement(
        self,
        workspace_id: str,
        *,
        subject_id: str,
        surface_phrase: str,
        object_entity_id: str | None,
        object_value: str | None,
        status: str,
        proposed_by: str,
        chunk_id: str,
        quote: str,
        quote_start: int | None = None,
        quote_end: int | None = None,
        confidence: float | None = None,
    ) -> str:
        if bool(object_entity_id) == bool(object_value):
            raise AdminError(422, "bad_statement", "陈述必须指定对象实体或对象值之一")
        if status not in {"pending", "confirmed", "rejected", "invalidated", "superseded"}:
            raise AdminError(422, "bad_status", "陈述状态无效")
        statement_id = str(uuid.uuid4())
        evidence_id = str(uuid.uuid4())
        now = _now()
        with self._store._lock:
            conn = self._store._conn
            self._store._assert_row_in_workspace("entities", subject_id, workspace_id)
            if object_entity_id:
                self._store._assert_row_in_workspace("entities", object_entity_id, workspace_id)
            self._store._assert_row_in_workspace("chunks", chunk_id, workspace_id)
            if quote_start is not None and quote_end is not None:
                chunk_persist.validate_quote_in_chunk(
                    conn, chunk_id, quote, quote_start, quote_end
                )
            stmt_persist.insert_statement_with_evidence(
                conn,
                statement_id=statement_id,
                workspace_id=workspace_id,
                subject_id=subject_id,
                surface_phrase=surface_phrase,
                object_entity_id=object_entity_id,
                object_value=object_value,
                confidence=confidence,
                status=status,
                proposed_by=proposed_by,
                recorded_at=now,
                evidence_id=evidence_id,
                chunk_id=chunk_id,
                quote=quote,
                quote_start=quote_start,
                quote_end=quote_end,
            )
            conn.commit()
        return statement_id

    def create_chunk(
        self,
        workspace_id: str,
        version_id: str,
        *,
        ordinal: int,
        text: str,
        heading: str | None = None,
        char_start: int | None = None,
        char_end: int | None = None,
        token_count: int | None = None,
        language: str | None = None,
        origin: str = "stated",
        anchor_json: str | None = None,
    ) -> str:
        chunk_id = str(uuid.uuid4())
        with self._store._lock:
            self._store._assert_row_in_workspace("document_versions", version_id, workspace_id)
            chunk_persist.insert_chunk(
                self._store._conn,
                chunk_id=chunk_id,
                workspace_id=workspace_id,
                version_id=version_id,
                ordinal=ordinal,
                text=text,
                heading=heading,
                char_start=char_start,
                char_end=char_end,
                token_count=token_count,
                language=language,
                origin=origin or "stated",
                anchor_json=anchor_json,
                created_at=_now(),
            )
            self._store._conn.commit()
        return chunk_id

    def create_chunks(
        self,
        workspace_id: str,
        version_id: str,
        texts: list[str] | list[dict[str, Any]],
    ) -> list[str]:
        if not texts:
            return []
        now = _now()
        chunk_ids = [str(uuid.uuid4()) for _ in texts]
        rows = []
        for ordinal, (chunk_id, item) in enumerate(zip(chunk_ids, texts)):
            payload = chunk_persist.chunk_payload_from_item(item)
            rows.append(
                (
                    chunk_id,
                    workspace_id,
                    version_id,
                    ordinal,
                    payload["text"],
                    payload["heading"],
                    payload["char_start"],
                    payload["char_end"],
                    payload["token_count"],
                    payload["language"],
                    payload["origin"],
                    payload["anchor_json"],
                    now,
                )
            )
        with self._store._lock:
            self._store._assert_row_in_workspace("document_versions", version_id, workspace_id)
            chunk_persist.insert_chunks_many(self._store._conn, rows)
            self._store._conn.commit()
        return chunk_ids

    def set_statement_status(self, workspace_id: str, statement_id: str, status: str) -> None:
        allowed = {"pending", "confirmed", "rejected", "invalidated", "superseded"}
        if status not in allowed:
            raise AdminError(422, "bad_status", "陈述状态无效")
        now = _now()
        with self._store._lock:
            conn = self._store._conn
            row = stmt_persist.fetch_statement_workspace_status(conn, statement_id)
            if row is None:
                raise AdminError(404, "not_found", "陈述不存在")
            if row["workspace_id"] != workspace_id:
                raise AdminError(403, "forbidden", "记录不属于该工作区")
            if row["status"] != "pending" and status in {"confirmed", "rejected"}:
                raise AdminError(409, "statement_not_pending", "陈述已处理")
            invalidated_at = now if status in {"invalidated", "rejected", "superseded"} else None
            stmt_persist.update_statement_status(
                conn, workspace_id, statement_id, status, invalidated_at
            )
            conn.commit()

    def invalidate_statement(self, workspace_id: str, statement_id: str) -> None:
        now = _now()
        with self._store._lock:
            conn = self._store._conn
            row = stmt_persist.fetch_statement_for_workspace(conn, statement_id)
            if row is None:
                raise AdminError(404, "not_found", "陈述不存在")
            if row["workspace_id"] != workspace_id:
                raise AdminError(403, "forbidden", "记录不属于该工作区")
            stmt_persist.invalidate_statement_row(conn, workspace_id, statement_id, now)
            conn.commit()
