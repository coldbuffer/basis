"""Workspace API for SQL catalog sources."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from basis.services.errors import AdminError
from basis.services.knowledge.store import KnowledgeStore
from basis.services.sql_catalog.engines.registry import (
    _redact,
    create_connector,
    supported_schemes,
)
from basis.services.sql_catalog.persist import (
    delete_source_row,
    fetch_snapshot_row,
    fetch_source_row,
    list_source_rows,
    upsert_snapshot_row,
    upsert_source_row,
)
from basis.services.sql_catalog.snapshot import collect_catalog
from basis.services.sql_catalog.table_filter import InvalidTableFilterError, from_connection

logger = logging.getLogger(__name__)

_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _failure_text(exc: BaseException, connection_uri: str) -> str:
    text = " ".join(str(exc).split()) or exc.__class__.__name__
    redacted = _redact(connection_uri)
    if connection_uri and connection_uri in text:
        text = text.replace(connection_uri, redacted)
    parsed = urlparse(connection_uri)
    if parsed.password and parsed.password in text:
        text = text.replace(parsed.password, "***")
    if len(text) > 280:
        text = text[:279].rstrip() + "…"
    return text


def _probe_connection(connection_uri: str) -> None:
    """Open the database and run a trivial query. Nothing is stored."""
    try:
        connector = create_connector(connection_uri)
    except ModuleNotFoundError as exc:
        raise AdminError(400, "sql_catalog_driver_missing", f"数据库驱动未安装：{exc.name}") from exc
    except Exception as exc:
        raise AdminError(
            400,
            "sql_catalog_connect_failed",
            _failure_text(exc, connection_uri),
        ) from exc
    try:
        connector.execute("SELECT 1")
    except Exception as exc:
        logger.exception("SQL catalog connection probe failed for %s", _redact(connection_uri))
        raise AdminError(
            400,
            "sql_catalog_connect_failed",
            _failure_text(exc, connection_uri),
        ) from exc
    finally:
        try:
            connector.close()
        except Exception:
            logger.exception("Failed to close SQL catalog probe for %s", _redact(connection_uri))


def _scheme(connection_uri: str) -> str:
    parsed = urlparse(connection_uri)
    if not parsed.scheme:
        raise AdminError(422, "bad_connection_uri", "连接串缺少协议")
    return parsed.scheme.split("+", 1)[0].lower()


def _config_from_fields(
    *,
    table_allow_regex: str | None,
    table_deny_regex: str | None,
    schemas: list[str] | None,
) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if table_allow_regex and table_allow_regex.strip():
        config["table_allow_regex"] = table_allow_regex.strip()
    if table_deny_regex and table_deny_regex.strip():
        config["table_deny_regex"] = table_deny_regex.strip()
    if schemas:
        cleaned = [str(item).strip() for item in schemas if str(item).strip()]
        if cleaned:
            config["schemas"] = cleaned
    try:
        from_connection(config)
    except InvalidTableFilterError as exc:
        raise AdminError(422, "invalid_table_filter", str(exc)) from exc
    return config


def _snapshot_counts(row: Any) -> dict[str, int] | None:
    if "payload_json" not in row.keys() or not row["payload_json"]:
        return None
    catalog = json.loads(row["payload_json"])
    return {
        "tables": len(catalog.get("tables") or []),
        "columns": len(catalog.get("columns") or []),
    }


def _public_source(row: Any, *, extracted_at: str | None = None) -> dict[str, Any]:
    config = json.loads(row["config_json"] or "{}")
    return {
        "source_id": row["source_id"],
        "display_name": row["display_name"],
        "scheme": _scheme(row["connection_uri"]),
        "connection_uri": _redact(row["connection_uri"]),
        "config": config,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "extracted_at": row["extracted_at"] if "extracted_at" in row.keys() else extracted_at,
        "counts": _snapshot_counts(row),
    }


def _public_snapshot(row: Any) -> dict[str, Any]:
    catalog = json.loads(row["payload_json"])
    return {
        "source_id": row["source_id"],
        "extracted_at": row["extracted_at"],
        "database_name": row["database_name"],
        "dialect": row["dialect"],
        "counts": {
            "tables": len(catalog.get("tables") or []),
            "columns": len(catalog.get("columns") or []),
            "views": len(catalog.get("views") or []),
            "primary_keys": len(catalog.get("primary_keys") or []),
            "foreign_keys": len(catalog.get("foreign_keys") or []),
            "queries": len(catalog.get("queries") or []),
        },
        "catalog": catalog,
    }


class SqlCatalogAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def list_sources(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            rows = list_source_rows(self._store._conn, workspace_id)
        return [_public_source(row) for row in rows]

    def test_connection(self, connection_uri: str) -> None:
        connection_uri = connection_uri.strip()
        if not connection_uri:
            raise AdminError(422, "bad_connection_uri", "连接串不能为空")
        scheme = _scheme(connection_uri)
        if scheme not in supported_schemes():
            raise AdminError(422, "unsupported_engine", f"不支持的数据库类型：{scheme}")
        _probe_connection(connection_uri)

    def upsert_source(
        self,
        workspace_id: str,
        source_id: str,
        *,
        display_name: str,
        connection_uri: str,
        table_allow_regex: str | None = None,
        table_deny_regex: str | None = None,
        schemas: list[str] | None = None,
    ) -> dict[str, Any]:
        if not _SOURCE_ID.match(source_id):
            raise AdminError(422, "bad_source_id", "来源 id 只能包含字母、数字、下划线和短横线")
        display_name = display_name.strip()
        connection_uri = connection_uri.strip()
        if not display_name:
            raise AdminError(422, "bad_name", "来源名称不能为空")
        if not connection_uri:
            raise AdminError(422, "bad_connection_uri", "连接串不能为空")
        scheme = _scheme(connection_uri)
        if scheme not in supported_schemes():
            raise AdminError(422, "unsupported_engine", f"不支持的数据库类型：{scheme}")
        config = _config_from_fields(
            table_allow_regex=table_allow_regex,
            table_deny_regex=table_deny_regex,
            schemas=schemas,
        )
        _probe_connection(connection_uri)
        now = _now()
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            existing = fetch_source_row(self._store._conn, workspace_id, source_id)
            upsert_source_row(
                self._store._conn,
                workspace_id=workspace_id,
                source_id=source_id,
                display_name=display_name,
                connection_uri=connection_uri,
                config_json=json.dumps(config, ensure_ascii=False),
                created_at=existing["created_at"] if existing is not None else now,
                updated_at=now,
            )
            self._store._conn.commit()
            row = fetch_source_row(self._store._conn, workspace_id, source_id)
            snap = fetch_snapshot_row(self._store._conn, workspace_id, source_id)
        public = _public_source(row, extracted_at=None)
        public["extracted_at"] = snap["extracted_at"] if snap is not None else None
        return public

    def delete_source(self, workspace_id: str, source_id: str) -> None:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            existing = fetch_source_row(self._store._conn, workspace_id, source_id)
            if existing is None:
                raise AdminError(404, "not_found", "目录来源不存在")
            delete_source_row(self._store._conn, workspace_id, source_id)
            self._store._conn.commit()

    def get_snapshot(self, workspace_id: str, source_id: str) -> dict[str, Any]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            if fetch_source_row(self._store._conn, workspace_id, source_id) is None:
                raise AdminError(404, "not_found", "目录来源不存在")
            row = fetch_snapshot_row(self._store._conn, workspace_id, source_id)
        if row is None:
            raise AdminError(404, "not_found", "还没有目录快照")
        return _public_snapshot(row)

    def snapshot_for_ontology(self, workspace_id: str, source_id: str) -> dict[str, Any]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            source = fetch_source_row(self._store._conn, workspace_id, source_id)
            row = fetch_snapshot_row(self._store._conn, workspace_id, source_id)
        if source is None:
            raise AdminError(404, "not_found", "目录来源不存在")
        if row is None:
            raise AdminError(404, "not_found", "还没有目录快照")
        return {
            "source_id": source_id,
            "display_name": source["display_name"],
            "catalog": json.loads(row["payload_json"]),
        }

    def snapshot_source(self, workspace_id: str, source_id: str) -> dict[str, Any]:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            source = fetch_source_row(self._store._conn, workspace_id, source_id)
        if source is None:
            raise AdminError(404, "not_found", "目录来源不存在")
        connection_uri = source["connection_uri"]
        config = json.loads(source["config_json"] or "{}")
        table_filter = from_connection(config)
        schemas = config.get("schemas")
        schema_list = schemas if isinstance(schemas, list) else None
        try:
            connector = create_connector(
                connection_uri,
                schemas=schema_list,
                table_filter=table_filter,
            )
            try:
                catalog = collect_catalog(connector, table_filter)
            finally:
                connector.close()
        except AdminError:
            raise
        except Exception as exc:
            logger.exception("SQL catalog snapshot failed for %s", _redact(connection_uri))
            if isinstance(exc, ModuleNotFoundError):
                raise AdminError(
                    400,
                    "sql_catalog_driver_missing",
                    f"数据库驱动未安装：{exc.name}",
                ) from exc
            raise AdminError(
                400,
                "sql_catalog_connect_failed",
                f"无法读取目录：{_redact(connection_uri)}",
            ) from exc
        extracted_at = _now()
        database_name = str(catalog.pop("database_name"))
        dialect = str(catalog.pop("dialect"))
        with self._store._lock:
            if fetch_source_row(self._store._conn, workspace_id, source_id) is None:
                raise AdminError(404, "not_found", "目录来源不存在")
            upsert_snapshot_row(
                self._store._conn,
                workspace_id=workspace_id,
                source_id=source_id,
                extracted_at=extracted_at,
                database_name=database_name,
                dialect=dialect,
                payload=catalog,
            )
            self._store._conn.commit()
            row = fetch_snapshot_row(self._store._conn, workspace_id, source_id)
        return _public_snapshot(row)
