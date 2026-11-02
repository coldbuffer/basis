"""Document upload, listing, and resolution — KnowledgeStore API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.services.errors import AdminError
from basis.services.knowledge.models import StoreDocumentOutcome
from basis.services.knowledge.persistence import sql_chunks as chunk_persist
from basis.services.knowledge.persistence import sql_documents as doc_persist

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uploaded_filename(title: str | None, external_key: str | None) -> str | None:
    name = (title or "").strip()
    if not name:
        return None
    key = (external_key or "").strip()
    if key and name == f"{key}.txt":
        return None
    return name


def document_ref_from_row(row: Any) -> dict[str, Any]:
    return {
        "document_id": row["document_id"],
        "external_key": row["external_key"],
        "version_id": row["version_id"],
    }


class DocumentsAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def store_upload_bytes(
        self,
        workspace_id: str,
        *,
        title: str,
        mime_type: str,
        data: bytes,
        created_by: str | None,
        original_filename: str | None = None,
        external_key: str | None = None,
    ) -> tuple[str, str, str, Any]:
        outcome = self.store_document_bytes(
            workspace_id,
            title=title,
            mime_type=mime_type,
            data=data,
            created_by=created_by,
            original_filename=original_filename,
            external_key=external_key,
        )
        job, _ = self._store.create_processing_job(
            workspace_id, version_id=outcome.version_id, options={}
        )
        return outcome.document_id, outcome.version_id, job["id"], outcome.blob

    def store_document_bytes(
        self,
        workspace_id: str,
        *,
        title: str,
        mime_type: str,
        data: bytes,
        created_by: str | None,
        original_filename: str | None = None,
        external_key: str | None = None,
        document_id: str | None = None,
        source_id: str | None = None,
    ) -> StoreDocumentOutcome:
        title = title.strip() or (original_filename or "upload").strip() or "upload"
        if len(title) > 256:
            raise AdminError(422, "bad_name", "标题过长")

        target_document_id = document_id
        if target_document_id is None and external_key:
            existing = self.find_document_by_external_key(workspace_id, external_key)
            if existing is not None:
                target_document_id = existing["document_id"]

        if target_document_id is not None:
            return self.append_document_version(
                workspace_id,
                target_document_id,
                title=title,
                mime_type=mime_type,
                data=data,
                created_by=created_by,
            )

        blob = self._store._blob_store.put(workspace_id, data)
        new_document_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        now = _now()

        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            conn = self._store._conn
            doc_persist.insert_document(
                conn,
                document_id=new_document_id,
                workspace_id=workspace_id,
                source_id=source_id,
                external_key=external_key,
                title=title,
                mime_type=mime_type,
                created_by=created_by,
                created_at=now,
            )
            doc_persist.insert_document_version(
                conn,
                version_id=version_id,
                workspace_id=workspace_id,
                document_id=new_document_id,
                version_no=1,
                sha256=blob.sha256,
                blob_key=blob.blob_key,
                byte_size=blob.byte_size,
                created_at=now,
            )
            doc_persist.set_document_current_version(conn, version_id, new_document_id, workspace_id)
            conn.commit()
        return StoreDocumentOutcome(
            document_id=new_document_id,
            version_id=version_id,
            blob=blob,
            version_no=1,
            new_document=True,
            new_version=True,
        )

    def append_document_version(
        self,
        workspace_id: str,
        document_id: str,
        *,
        title: str,
        mime_type: str,
        data: bytes,
        created_by: str | None,
    ) -> StoreDocumentOutcome:
        blob = self._store._blob_store.put(workspace_id, data)
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            conn = self._store._conn
            doc = doc_persist.fetch_document_for_append(conn, document_id, workspace_id)
            if doc is None:
                raise AdminError(404, "not_found", "文档不存在")
            current_version_id = doc["current_version_id"]
            if not current_version_id:
                raise AdminError(409, "no_current_version", "文档没有当前版本")
            if self._store._processing.has_active_ingest_job(workspace_id, current_version_id):
                raise AdminError(409, "processing_active", "当前版本正在处理，请稍后再更新")

            current = doc_persist.fetch_version_for_append(
                conn, current_version_id, workspace_id, document_id
            )
            if current is None:
                raise AdminError(409, "no_current_version", "文档没有当前版本")

            if current["sha256"] == blob.sha256:
                conn.commit()
                return StoreDocumentOutcome(
                    document_id=document_id,
                    version_id=current_version_id,
                    blob=blob,
                    version_no=int(current["version_no"]),
                    new_document=False,
                    new_version=False,
                )

            version_no = doc_persist.next_version_no(conn, workspace_id, document_id)
            version_id = str(uuid.uuid4())
            self._store._processing.supersede_version(workspace_id, current_version_id)
            doc_persist.insert_document_version(
                conn,
                version_id=version_id,
                workspace_id=workspace_id,
                document_id=document_id,
                version_no=version_no,
                sha256=blob.sha256,
                blob_key=blob.blob_key,
                byte_size=blob.byte_size,
                created_at=now,
            )
            doc_persist.update_document_after_append(
                conn,
                version_id=version_id,
                title=title,
                mime_type=mime_type,
                document_id=document_id,
                workspace_id=workspace_id,
            )
            conn.commit()
        return StoreDocumentOutcome(
            document_id=document_id,
            version_id=version_id,
            blob=blob,
            version_no=version_no,
            new_document=False,
            new_version=True,
        )

    def get_document_summary(self, workspace_id: str, doc_ref: str) -> dict[str, Any] | None:
        doc = self.resolve_document_ref(workspace_id, doc_ref)
        if doc is None:
            return None
        with self._store._lock:
            row = doc_persist.fetch_document_summary_row(
                self._store._conn, workspace_id, doc["document_id"]
            )
        if row is None:
            return None
        doc_id = row["external_key"] or doc["document_id"]
        return {
            **doc,
            "doc_id": doc_id,
            "title": row["title"] or doc_id,
            "version_status": row["version_status"],
        }

    def resolve_document_ref(self, workspace_id: str, doc_ref: str) -> dict[str, Any] | None:
        doc_ref = doc_ref.strip()
        if not doc_ref:
            return None
        by_key = self.find_document_by_external_key(workspace_id, doc_ref)
        if by_key is not None:
            return by_key
        with self._store._lock:
            row = doc_persist.find_document_ref_by_id(self._store._conn, workspace_id, doc_ref)
        if row is None:
            return None
        return document_ref_from_row(row)

    def find_document_by_external_key(
        self, workspace_id: str, external_key: str
    ) -> dict[str, Any] | None:
        with self._store._lock:
            row = doc_persist.find_document_ref_by_external_key(
                self._store._conn, workspace_id, external_key
            )
        if row is None:
            return None
        return document_ref_from_row(row)

    def first_chunk_id_for_version(self, workspace_id: str, version_id: str) -> str | None:
        with self._store._lock:
            return chunk_persist.first_chunk_id(self._store._conn, workspace_id, version_id)

    def ensure_legacy_document(
        self,
        workspace_id: str,
        *,
        external_key: str,
        title: str,
        text: str,
    ) -> tuple[dict[str, Any], str, bool]:
        existing = self.find_document_by_external_key(workspace_id, external_key)
        if existing and existing["version_id"]:
            chunk_id = self.first_chunk_id_for_version(workspace_id, existing["version_id"])
            if chunk_id:
                return existing, chunk_id, False

        document_id, version_id, job_id, _blob = self.store_upload_bytes(
            workspace_id,
            title=title,
            mime_type="text/plain",
            data=text.encode("utf-8"),
            created_by=None,
            original_filename=title,
            external_key=external_key,
        )
        self._store.set_version_status(workspace_id, version_id, "ready")
        self._store.set_job_status(workspace_id, job_id, "succeeded")
        chunk_id = self._store.create_chunk(workspace_id, version_id, ordinal=0, text=text)
        row = {
            "document_id": document_id,
            "external_key": external_key,
            "version_id": version_id,
        }
        return row, chunk_id, True

    def list_documents(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._store._lock:
            rows = doc_persist.list_document_rows(self._store._conn, workspace_id)
            items: list[dict[str, Any]] = []
            conn = self._store._conn
            for row in rows:
                doc_id = row["external_key"] or row["id"]
                preview = ""
                char_count = 0
                if row["version_id"]:
                    chunk = chunk_persist.first_chunk_text(conn, workspace_id, row["version_id"])
                    if chunk:
                        preview = (chunk["text"] or "")[:200]
                        char_count = len(chunk["text"] or "")
                items.append(
                    {
                        "doc_id": doc_id,
                        "document_id": row["id"],
                        "filename": uploaded_filename(row["title"], row["external_key"]),
                        "preview": preview,
                        "char_count": char_count,
                        "version_status": row["version_status"],
                        "version_id": row["version_id"],
                        "version_no": row["version_no"],
                        "created_at": row["created_at"],
                        "updated_at": row["version_created_at"] or row["created_at"],
                    }
                )
        return items

    def read_version_bytes(self, workspace_id: str, version_id: str) -> bytes:
        version = self._store.get_version(workspace_id, version_id)
        return self._store._blob_store.read(version.workspace_id, version.blob_key)

    def list_chunks_for_version(self, workspace_id: str, version_id: str) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_row_in_workspace("document_versions", version_id, workspace_id)
            rows = chunk_persist.list_chunk_rows(self._store._conn, workspace_id, version_id)
        return [chunk_persist.chunk_api_row(r) for r in rows]
