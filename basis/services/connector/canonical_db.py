"""Resolve KnowledgeStore (or legacy connection) for BOCP persistence."""

from __future__ import annotations

from typing import Any


def is_knowledge_store(db: Any) -> bool:
    return hasattr(db, "_conn") and hasattr(db, "_lock") and hasattr(db, "connector_runtime")


def canonical_conn(db: Any) -> Any:
    """Return the DB-API connection for a store or pass through a raw connection."""
    if is_knowledge_store(db):
        return db._conn
    return db


class LockedCanonicalConn:
    """Execute SQL on the canonical DB, serializing through KnowledgeStore.lock when present."""

    def __init__(self, knowledge_or_conn: Any) -> None:
        self._store = knowledge_or_conn if is_knowledge_store(knowledge_or_conn) else None
        self._conn = canonical_conn(knowledge_or_conn)

    def execute(self, sql: str, params: Any = ()) -> Any:
        if self._store is not None:
            with self._store._lock:
                return self._store._conn.execute(sql, params)
        return self._conn.execute(sql, params)

    def commit(self) -> None:
        if self._store is not None:
            with self._store._lock:
                self._conn.commit()
        else:
            self._conn.commit()

    def get_platform_allowed_providers(self) -> list[str] | str:
        from basis.services.connector.vault.platform_policy import PlatformConnectorPolicy

        if self._store is not None:
            with self._store._lock:
                return PlatformConnectorPolicy(self._conn).get_allowed_providers()
        return PlatformConnectorPolicy(self._conn).get_allowed_providers()

    def upsert_platform_allowed_providers(
        self,
        allowed_providers: list[str] | str,
    ) -> tuple[list[str] | str, str]:
        from basis.services.connector.vault.platform_policy import PlatformConnectorPolicy

        if self._store is not None:
            with self._store._lock:
                return PlatformConnectorPolicy(self._conn).upsert_allowed_providers(
                    allowed_providers
                )
        return PlatformConnectorPolicy(self._conn).upsert_allowed_providers(
            allowed_providers
        )
