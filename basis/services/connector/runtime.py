"""Unified BOCP runtime engine routing CHECK, DISCOVER, READ, and MUTATE across SQL and REST adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from basis.services.connector.vault.auth_vault import ConnectorAuthVault, StoredConnection
from basis.services.connector.vault.connection_scope import (
    SCOPE_WORKSPACE,
    ConnectionScope,
    normalize_connection_scope,
    normalize_subject_id,
)
from basis.services.connector.registry import ConnectorCatalog, get_connector_catalog
from basis.services.connector.manifest.manifest_schema import (
    ConnectorManifest,
    StreamFieldSpec,
    StreamSpec,
    ToolSpec,
)
from basis.services.connector.adapters.mail import MailAdapter
from basis.services.connector.adapters.mail.credentials import MAIL_CREDENTIAL_READERS
from basis.services.connector.adapters.rest import (
    RestBatchResult,
    RestDeclarativeStreamAdapter,
)
from basis.services.connector.adapters.sql import (
    DiscoveredTableSchema,
    SqlAlchemyStreamAdapter,
)
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DiscoveredStreamInfo:
    stream_name: str
    display_name: str
    external_table: str
    primary_key: list[str]
    cursor_field: str | None = None
    fields: list[StreamFieldSpec] = field(default_factory=list)


@dataclass
class UnifiedReadResult:
    records: list[dict[str, Any]]
    next_cursor_value: Any | None = None
    has_more: bool = False


class ConnectorRuntime:
    """High-level BOCP runtime executing the 4 primitives with policy checks and audit logging."""

    def __init__(
        self,
        knowledge_or_conn: Any,
        *,
        catalog: ConnectorCatalog | None = None,
        vault_secret: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.catalog = catalog or get_connector_catalog()
        self.vault = ConnectorAuthVault(knowledge_or_conn, vault_secret=vault_secret)
        self._http_client = http_client

    def _require_manifest_and_connection(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
    ) -> tuple[ConnectorManifest, StoredConnection]:
        self.vault.assert_service_allowed(workspace_id, service)
        manifest = self.catalog.get(service)
        if not manifest:
            raise ValueError(f"Unknown BOCP connector service: {service}")
        scope = normalize_connection_scope(
            connection_scope if isinstance(connection_scope, str) else connection_scope
        )
        sid = normalize_subject_id(subject_id, scope=scope)
        connection = self.vault.get_connection(
            workspace_id,
            service,
            connection_scope=scope,
            subject_id=sid,
        )
        if not connection:
            raise LookupError(
                f"Connection not found for service '{service}' in workspace '{workspace_id}'"
            )
        return manifest, connection

    @staticmethod
    def _is_sql_stream(stream: StreamSpec) -> bool:
        return stream.retriever.adapter == "sql_alchemy"

    @staticmethod
    def _is_mail_service(manifest: ConnectorManifest) -> bool:
        if manifest.service in MAIL_CREDENTIAL_READERS:
            return True
        return manifest.spec is not None and manifest.spec.protocol == "mail"

    def check_connection(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
    ) -> dict[str, Any]:
        """Run `CHECK` primitive, update connection account_profile, and log run."""
        started_at = _now_iso()
        manifest, connection = self._require_manifest_and_connection(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
        )
        try:
            if self._is_mail_service(manifest):
                mail_adapter = MailAdapter()
                profile = mail_adapter.check_connection(manifest, connection)
            elif manifest.streams and self._is_sql_stream(manifest.streams[0]):
                sql_adapter = SqlAlchemyStreamAdapter.from_connection(connection)
                try:
                    profile = sql_adapter.check_connection()
                finally:
                    sql_adapter.close()
            else:
                rest_adapter = RestDeclarativeStreamAdapter(
                    self.vault, http_client=self._http_client
                )
                try:
                    profile = rest_adapter.check_connection(manifest, connection)
                finally:
                    rest_adapter.close()

            self.vault.upsert_connection(
                workspace_id,
                service,
                connection_scope=connection.connection_scope,
                subject_id=connection.subject_id,
                auth_type=connection.auth_type,
                account_profile=profile,
            )
            self.vault.record_run(
                workspace_id,
                service=service,
                operation_kind="check",
                target_id=service,
                started_at=started_at,
                ok=True,
                value=profile,
            )
            return profile
        except Exception as exc:
            self.vault.record_run(
                workspace_id,
                service=service,
                operation_kind="check",
                target_id=service,
                started_at=started_at,
                ok=False,
                value={"error": str(exc)},
            )
            raise

    def discover_schema(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
        stream_name: str | None = None,
        external_table: str | None = None,
        stream_params: dict[str, Any] | None = None,
    ) -> DiscoveredStreamInfo:
        """Run `DISCOVER` primitive for a SQL table or REST stream."""
        manifest, connection = self._require_manifest_and_connection(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
        )
        stream = self._find_stream(manifest, stream_name)
        if self._is_sql_stream(stream):
            if not external_table:
                raise ValueError("external_table is required for SQL schema discovery")
            sql_adapter = SqlAlchemyStreamAdapter.from_connection(connection)
            try:
                tbl: DiscoveredTableSchema = sql_adapter.discover_table_schema(
                    external_table
                )
                return DiscoveredStreamInfo(
                    stream_name=stream.name,
                    display_name=external_table,
                    external_table=external_table,
                    primary_key=tbl.primary_key or list(stream.primary_key),
                    cursor_field=stream.cursor_field,
                    fields=tbl.fields,
                )
            finally:
                sql_adapter.close()

        rest_adapter = RestDeclarativeStreamAdapter(
            self.vault, http_client=self._http_client
        )
        try:
            fields = rest_adapter.discover_stream_schema(
                manifest,
                connection,
                stream,
                stream_params=stream_params,
            )
            return DiscoveredStreamInfo(
                stream_name=stream.name,
                display_name=stream.display_name,
                external_table=external_table or stream.name,
                primary_key=list(stream.primary_key),
                cursor_field=stream.cursor_field,
                fields=fields,
            )
        finally:
            rest_adapter.close()

    def read_stream(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
        stream_name: str | None = None,
        external_table: str | None = None,
        primary_key_column: str = "id",
        cursor_column: str | None = None,
        cursor_watermark: Any | None = None,
        stream_params: dict[str, Any] | None = None,
        limit: int = 500,
    ) -> UnifiedReadResult:
        """Run `READ` primitive across SQL or REST streams."""
        started_at = _now_iso()
        manifest, connection = self._require_manifest_and_connection(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
        )
        stream = self._find_stream(manifest, stream_name)
        target_label = external_table or stream.name

        try:
            if self._is_sql_stream(stream):
                if not external_table:
                    raise ValueError("external_table is required for SQL stream read")
                sql_adapter = SqlAlchemyStreamAdapter.from_connection(connection)
                try:
                    sql_res = sql_adapter.read_records(
                        external_table,
                        primary_key_column=primary_key_column,
                        cursor_column=cursor_column,
                        cursor_watermark=cursor_watermark,
                        limit=limit,
                    )
                    res = UnifiedReadResult(
                        records=sql_res.records,
                        next_cursor_value=sql_res.next_cursor_value,
                        has_more=sql_res.has_more,
                    )
                finally:
                    sql_adapter.close()
            else:
                rest_adapter = RestDeclarativeStreamAdapter(
                    self.vault, http_client=self._http_client
                )
                try:
                    rest_res: RestBatchResult = rest_adapter.read_stream_records(
                        manifest,
                        connection,
                        stream,
                        stream_params=stream_params,
                        cursor_watermark=cursor_watermark,
                        max_records=limit,
                    )
                    res = UnifiedReadResult(
                        records=rest_res.records,
                        next_cursor_value=rest_res.next_cursor_value,
                        has_more=rest_res.has_more,
                    )
                finally:
                    rest_adapter.close()

            self.vault.record_run(
                workspace_id,
                service=service,
                operation_kind="read_stream",
                target_id=target_label,
                started_at=started_at,
                ok=True,
                value={"records_count": len(res.records)},
            )
            return res
        except Exception as exc:
            self.vault.record_run(
                workspace_id,
                service=service,
                operation_kind="read_stream",
                target_id=target_label,
                started_at=started_at,
                ok=False,
                value={"error": str(exc)},
            )
            raise

    def mutate_stream(
        self,
        workspace_id: str,
        service: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
        stream_name: str | None = None,
        external_table: str | None = None,
        operation: str = "update",
        primary_key_column: str = "id",
        external_pk: Any,
        changes: dict[str, Any],
        stream_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run `MUTATE` primitive across SQL or REST streams and record audit log."""
        started_at = _now_iso()
        manifest, connection = self._require_manifest_and_connection(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
        )
        stream = self._find_stream(manifest, stream_name)
        target_label = f"{external_table or stream.name}:{external_pk}"

        try:
            if self._is_sql_stream(stream):
                if not external_table:
                    raise ValueError("external_table is required for SQL mutation")
                sql_adapter = SqlAlchemyStreamAdapter.from_connection(connection)
                try:
                    out = sql_adapter.mutate_record(
                        external_table,
                        operation=operation,
                        primary_key_column=primary_key_column,
                        external_pk=external_pk,
                        changes=changes,
                    )
                finally:
                    sql_adapter.close()
            else:
                rest_adapter = RestDeclarativeStreamAdapter(
                    self.vault, http_client=self._http_client
                )
                try:
                    out = rest_adapter.mutate_stream_record(
                        manifest,
                        connection,
                        stream,
                        operation=operation,
                        external_id=str(external_pk),
                        patch=changes,
                        stream_params=stream_params,
                    )
                finally:
                    rest_adapter.close()

            self.vault.record_run(
                workspace_id,
                service=service,
                operation_kind=f"mutate_{operation}",
                target_id=target_label,
                started_at=started_at,
                ok=True,
                value={"updated_fields": sorted(changes.keys())},
            )
            return out
        except Exception as exc:
            self.vault.record_run(
                workspace_id,
                service=service,
                operation_kind=f"mutate_{operation}",
                target_id=target_label,
                started_at=started_at,
                ok=False,
                value={"error": str(exc)},
            )
            raise

    @staticmethod
    def _find_stream(
        manifest: ConnectorManifest, stream_name: str | None
    ) -> StreamSpec:
        if not manifest.streams:
            raise ValueError(f"Service '{manifest.service}' defines no streams")
        if not stream_name:
            return manifest.streams[0]
        for s in manifest.streams:
            if s.name == stream_name:
                return s
        raise ValueError(
            f"Stream '{stream_name}' not found on service '{manifest.service}'"
        )

    @staticmethod
    def _find_tool(manifest: ConnectorManifest, tool_id: str) -> ToolSpec:
        for t in manifest.tools:
            if t.id == tool_id or t.name == tool_id:
                return t
        raise ValueError(
            f"Tool '{tool_id}' not found on service '{manifest.service}'"
        )

    def execute_tool(
        self,
        workspace_id: str,
        service: str,
        tool_id: str,
        *,
        connection_scope: ConnectionScope | str = SCOPE_WORKSPACE,
        subject_id: str | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run `TOOL` primitive with workspace action policy enforcement and audit logging."""
        started_at = _now_iso()
        manifest, connection = self._require_manifest_and_connection(
            workspace_id,
            service,
            connection_scope=connection_scope,
            subject_id=subject_id,
        )
        tool = self._find_tool(manifest, tool_id)
        procedure = manifest.get_procedure(tool_id)
        policy = self.vault.get_policy(workspace_id)
        mode = policy.resolve_tool_execution_mode(service, tool)
        if mode == "disabled":
            raise PermissionError(
                f"Tool '{tool.id}' on service '{service}' is disabled by workspace action policy"
            )

        try:
            if procedure.mail is not None:
                mail_adapter = MailAdapter()
                out = mail_adapter.execute_procedure(
                    manifest,
                    connection,
                    procedure,
                    arguments=arguments,
                )
            else:
                rest_adapter = RestDeclarativeStreamAdapter(
                    self.vault, http_client=self._http_client
                )
                try:
                    out = rest_adapter.execute_tool(
                        manifest,
                        connection,
                        tool,
                        arguments=arguments,
                    )
                finally:
                    rest_adapter.close()

            self.vault.record_run(
                workspace_id,
                service=service,
                operation_kind="tool",
                target_id=tool.id,
                started_at=started_at,
                ok=True,
                value={"tool_id": tool.id, "mode": mode},
            )
            return {"tool_id": tool.id, "mode": mode, "result": out}
        except Exception as exc:
            self.vault.record_run(
                workspace_id,
                service=service,
                operation_kind="tool",
                target_id=tool.id,
                started_at=started_at,
                ok=False,
                value={"error": str(exc)},
            )
            raise
