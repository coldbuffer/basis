"""BOCP entry points on KnowledgeStore (no SQL)."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from basis.services.knowledge.ports.connector import LockedCanonicalConn
from basis.services.knowledge.sql import ConnectorSyncPersistence, ConnectorVaultPersistence

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore


class ConnectorAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def connector_vault_persistence(self) -> ConnectorVaultPersistence:
        return ConnectorVaultPersistence(LockedCanonicalConn(self._store))

    def connector_sync_persistence(self) -> ConnectorSyncPersistence:
        return ConnectorSyncPersistence(LockedCanonicalConn(self._store))

    def get_platform_allowed_providers(self) -> list[str] | str:
        return LockedCanonicalConn(self._store).get_platform_allowed_providers()

    def connector_runtime(self):
        from basis.services.knowledge.ports.connector import ConnectorRuntime

        return ConnectorRuntime(self._store)

    def connector_sync_service(self):
        from basis.services.knowledge.services.connector_sync import ConnectorLedgerSyncService

        return ConnectorLedgerSyncService(self._store, self.connector_runtime())

    def list_source_table_mapping_ids(
        self,
        workspace_id: str,
        *,
        limit: int | None = None,
    ) -> list[str]:
        return self.connector_sync_persistence().list_mapping_ids(workspace_id, limit=limit)

    def list_entity_sync_outbox_ids(
        self,
        workspace_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[str]:
        return self.connector_sync_persistence().list_outbox_ids(
            workspace_id, status=status, limit=limit
        )

    def reject_entity_sync_outbox(self, workspace_id: str, outbox_id: str) -> None:
        self.connector_sync_persistence().reject_outbox(workspace_id, outbox_id)

    def list_connector_runs(
        self,
        workspace_id: str,
        *,
        service: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.connector_vault_persistence().list_connector_runs(
            workspace_id, service=service, limit=limit
        )

    def list_active_connector_table_mappings_global(self) -> list[tuple[str, str]]:
        return self.connector_sync_persistence().list_active_inbound_mapping_pairs()
