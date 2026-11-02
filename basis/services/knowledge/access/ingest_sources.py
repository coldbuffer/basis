"""Workspace ingest sources (webhook, poll, git, connector) — KnowledgeStore API."""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from basis.services.errors import AdminError
from basis.services.knowledge.persistence import sql_ingest_sources as source_persist

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore

INGEST_SOURCE_KINDS = frozenset({"webhook", "http_poll", "git", "connector"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestSourcesAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def list_scheduled_ingest_sources_global(self) -> list[dict[str, Any]]:
        with self._store._lock:
            rows = source_persist.list_scheduled_ingest_source_rows(self._store._conn)
        return [source_persist.ingest_source_row_to_dict(row) for row in rows]

    def list_http_poll_sources_global(self) -> list[dict[str, Any]]:
        return [
            s
            for s in self.list_scheduled_ingest_sources_global()
            if s["kind"] == "http_poll"
        ]

    def list_ingest_sources(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = source_persist.list_ingest_source_rows(self._store._conn, workspace_id)
        return [source_persist.ingest_source_row_to_dict(row) for row in rows]

    def create_ingest_source(
        self,
        workspace_id: str,
        actor_id: str,
        *,
        kind: str,
        name: str,
        config: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> tuple[dict[str, Any], str | None]:
        name = name.strip()
        if not name:
            raise AdminError(422, "bad_name", "来源名称不能为空")
        if kind not in INGEST_SOURCE_KINDS:
            raise AdminError(422, "bad_kind", "不支持的来源类型")
        config_payload = dict(config or {})
        if kind == "http_poll":
            url = str(config_payload.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                raise AdminError(422, "bad_url", "http_poll 需要有效的 http(s) URL")
        if kind == "git":
            repo = str(config_payload.get("repo_url") or "").strip()
            if not repo:
                raise AdminError(422, "bad_repo", "git 需要 repo_url")
            paths = config_payload.get("paths")
            if not isinstance(paths, list) or not any(str(p).strip() for p in paths):
                raise AdminError(422, "bad_paths", "git 需要至少一个 paths 文件路径")
        source_id = str(uuid.uuid4())
        now = _now()
        secret_ref: str | None = None
        one_time_secret: str | None = None
        if kind == "webhook":
            one_time_secret = secrets.token_urlsafe(32)
            secret_ref = one_time_secret
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            source_persist.insert_ingest_source(
                self._store._conn,
                source_id=source_id,
                workspace_id=workspace_id,
                kind=kind,
                name=name,
                config_json=json.dumps(config_payload),
                secret_ref=secret_ref,
                enabled=1 if enabled else 0,
                created_by=actor_id,
                created_at=now,
                updated_at=now,
            )
            self._store._conn.commit()
        return self.get_ingest_source(workspace_id, source_id), one_time_secret

    def get_ingest_source(self, workspace_id: str, source_id: str) -> dict[str, Any]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            row = source_persist.fetch_ingest_source_row(
                self._store._conn, workspace_id, source_id
            )
        if row is None:
            raise AdminError(404, "not_found", "来源不存在")
        return source_persist.ingest_source_row_to_dict(row)

    def get_ingest_source_secret(self, workspace_id: str, source_id: str) -> str | None:
        with self._store._lock:
            row = source_persist.fetch_ingest_source_secret(
                self._store._conn, workspace_id, source_id
            )
        if row is None:
            return None
        return row["secret_ref"]

    def update_ingest_source(
        self,
        workspace_id: str,
        source_id: str,
        *,
        name: str | None = None,
        enabled: bool | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            row = source_persist.fetch_ingest_source_for_update(
                self._store._conn, workspace_id, source_id
            )
            if row is None:
                raise AdminError(404, "not_found", "来源不存在")
            new_name = name.strip() if name is not None else row["name"]
            if not new_name:
                raise AdminError(422, "bad_name", "来源名称不能为空")
            merged_config = json.loads(row["config_json"])
            if config is not None:
                merged_config.update(config)
            new_enabled = (1 if enabled else 0) if enabled is not None else row["enabled"]
            now = _now()
            source_persist.update_ingest_source_row(
                self._store._conn,
                workspace_id,
                source_id,
                name=new_name,
                config_json=json.dumps(merged_config),
                enabled=new_enabled,
                updated_at=now,
            )
            self._store._conn.commit()
        return self.get_ingest_source(workspace_id, source_id)

    def delete_ingest_source(self, workspace_id: str, source_id: str) -> None:
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            n = source_persist.soft_delete_ingest_source(
                self._store._conn,
                workspace_id,
                source_id,
                deleted_at=now,
                updated_at=now,
            )
            self._store._conn.commit()
            if n == 0:
                raise AdminError(404, "not_found", "来源不存在")

    def rotate_ingest_source_token(self, workspace_id: str, source_id: str) -> str:
        source = self.get_ingest_source(workspace_id, source_id)
        if source["kind"] != "webhook":
            raise AdminError(422, "bad_kind", "仅 Webhook 来源可轮换令牌")
        new_token = secrets.token_urlsafe(32)
        now = _now()
        with self._store._lock:
            n = source_persist.rotate_ingest_source_secret(
                self._store._conn,
                workspace_id,
                source_id,
                secret_ref=new_token,
                updated_at=now,
            )
            self._store._conn.commit()
            if n == 0:
                raise AdminError(404, "not_found", "来源不存在")
        return new_token
