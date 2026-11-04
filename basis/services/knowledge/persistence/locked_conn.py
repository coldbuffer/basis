"""Serialize SQL against a KnowledgeStore lock."""

from __future__ import annotations

from typing import Any


def _is_knowledge_store(db: Any) -> bool:
    return hasattr(db, "_conn") and hasattr(db, "_lock")


class LockedCanonicalConn:
    """Execute SQL on the canonical DB, serializing through KnowledgeStore.lock when present."""

    def __init__(self, knowledge_or_conn: Any) -> None:
        self._store = knowledge_or_conn if _is_knowledge_store(knowledge_or_conn) else None
        self._conn = knowledge_or_conn._conn if self._store is not None else knowledge_or_conn

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
