"""Database engines shared by AdminStore and KnowledgeStore."""

from __future__ import annotations

import sqlite3
import threading
import re
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from basis.services.errors import AdminError
from basis.infra.db.alembic_upgrade import upgrade_postgres_engine, upgrade_sqlite_file
from basis.infra.db.sqlite_migrations import MigrationError, assert_desktop_sqlite_compatible
from basis.infra.runtime.sqlite_connection import connect_sqlite

_pool: dict[str, Database] = {}
_pool_guard = threading.Lock()


class CompatRow:
    """sqlite3.Row-compatible wrapper for SQLAlchemy result rows."""

    def __init__(self, keys: Sequence[str], values: Sequence[Any]) -> None:
        self._keys = tuple(keys)
        self._values = tuple(values)
        self._mapping = dict(zip(self._keys, self._values))

    def __getitem__(self, key: str | int) -> Any:
        return self._values[key] if isinstance(key, int) else self._mapping[key]

    def keys(self) -> list[str]:
        return list(self._keys)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)


class CompatResult:
    def __init__(
        self,
        rows: list[CompatRow] | None = None,
        *,
        rowcount: int = -1,
        lastrowid: Any = None,
    ) -> None:
        self._rows = rows or []
        self._index = 0
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    def fetchone(self) -> CompatRow | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self) -> list[CompatRow]:
        rows = self._rows[self._index :]
        self._index = len(self._rows)
        return rows


def _postgres_sql(sql: str) -> str:
    rewritten = re.sub(
        r"\bINSERT\s+OR\s+IGNORE\s+INTO\b",
        "INSERT INTO",
        sql,
        flags=re.IGNORECASE,
    )
    if re.search(r"\bINSERT\s+OR\s+IGNORE\b", sql, re.IGNORECASE):
        rewritten = rewritten.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return rewritten.replace("?", "%s")


class PostgresConnection:
    """Small DB-API compatibility facade over a pooled SQLAlchemy engine."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._local = threading.local()

    @staticmethod
    def _is_read(sql: str) -> bool:
        token = sql.lstrip().split(None, 1)[0].upper()
        return token in {"SELECT", "WITH", "EXPLAIN", "SHOW"}

    def execute(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] = ()
    ) -> CompatResult:
        statement = _postgres_sql(sql)
        if self._is_read(statement):
            active = getattr(self._local, "conn", None)
            if active is not None:
                result = active.exec_driver_sql(statement, params)
                keys = list(result.keys())
                rows = [CompatRow(keys, tuple(row)) for row in result.fetchall()]
                return CompatResult(rows, rowcount=result.rowcount)
            with self._engine.connect() as conn:
                result = conn.exec_driver_sql(statement, params)
                keys = list(result.keys())
                rows = [CompatRow(keys, tuple(row)) for row in result.fetchall()]
                return CompatResult(rows, rowcount=result.rowcount)
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._engine.connect()
            self._local.conn = conn
            self._local.tx = conn.begin()
        try:
            result = conn.exec_driver_sql(statement, params)
        except Exception:
            self.rollback()
            raise
        rows: list[CompatRow] = []
        if result.returns_rows:
            keys = list(result.keys())
            rows = [CompatRow(keys, tuple(row)) for row in result.fetchall()]
        return CompatResult(
            rows,
            rowcount=result.rowcount,
            lastrowid=getattr(result, "lastrowid", None),
        )

    def executemany(self, sql: str, params: Sequence[Sequence[Any]]) -> CompatResult:
        return self.execute(sql, list(params))

    def commit(self) -> None:
        tx = getattr(self._local, "tx", None)
        conn = getattr(self._local, "conn", None)
        if tx is not None:
            tx.commit()
        if conn is not None:
            conn.close()
        self._local.tx = None
        self._local.conn = None

    def rollback(self) -> None:
        tx = getattr(self._local, "tx", None)
        conn = getattr(self._local, "conn", None)
        if tx is not None:
            tx.rollback()
        if conn is not None:
            conn.close()
        self._local.tx = None
        self._local.conn = None

    def close(self) -> None:
        self.rollback()


class Database:
    backend: str
    lock: Any
    conn: Any

    def add_ref(self) -> None:
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError


class OperationLock:
    """Per-thread transaction boundary without serializing PostgreSQL callers."""

    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection
        self._local = threading.local()

    def __enter__(self) -> OperationLock:
        self._local.depth = getattr(self._local, "depth", 0) + 1
        return self

    def __exit__(self, exc_type: Any, *_args: Any) -> None:
        depth = getattr(self._local, "depth", 1) - 1
        self._local.depth = depth
        if depth == 0:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()


class SqliteDatabase(Database):
    """Thread-safe access to a single SQLite connection."""

    def __init__(self, path: Path) -> None:
        self.backend = "sqlite"
        self.path = path.resolve()
        self._lock = threading.RLock()
        try:
            upgrade_sqlite_file(self.path)
        except MigrationError as exc:
            raise AdminError(500, "migration_failed", exc.message) from exc
        except Exception as exc:
            raise AdminError(500, "migration_failed", str(exc)) from exc
        self._conn = connect_sqlite(self.path)
        try:
            assert_desktop_sqlite_compatible(self._conn)
        except MigrationError as exc:
            self._conn.close()
            raise AdminError(500, "migration_failed", exc.message) from exc
        self._refs = 0

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def add_ref(self) -> None:
        self._refs += 1

    def release(self) -> None:
        self._refs -= 1
        if self._refs <= 0:
            self._conn.close()
            with _pool_guard:
                _pool.pop(str(self.path), None)


class PostgresDatabase(Database):
    """Pooled PostgreSQL database; MVCC replaces the SQLite process lock."""

    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
    ) -> None:
        self.backend = "postgres"
        self.url = url
        self.path = Path(".")
        sqlalchemy_url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.engine = create_engine(
            sqlalchemy_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
        )
        try:
            upgrade_postgres_engine(self.engine)
        except Exception as exc:
            self.engine.dispose()
            raise AdminError(500, "migration_failed", str(exc)) from exc
        self._conn = PostgresConnection(self.engine)
        self._lock = OperationLock(self._conn)
        self._refs = 0

    @property
    def conn(self) -> PostgresConnection:
        return self._conn

    @property
    def lock(self) -> OperationLock:
        return self._lock

    def add_ref(self) -> None:
        self._refs += 1

    def release(self) -> None:
        self._refs -= 1
        if self._refs <= 0:
            self._conn.close()
            self.engine.dispose()
            with _pool_guard:
                _pool.pop(self.url, None)


def get_sqlite_database(path: Path) -> SqliteDatabase:
    key = str(path.resolve())
    with _pool_guard:
        db = _pool.get(key)
        if db is None:
            db = SqliteDatabase(path)
            _pool[key] = db
        db.add_ref()
        return db


def get_database(
    url: str,
    *,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_timeout: int = 30,
) -> Database:
    if url.startswith("sqlite:"):
        path_value = url.removeprefix("sqlite:///")
        return get_sqlite_database(Path(path_value))
    key = url
    with _pool_guard:
        db = _pool.get(key)
        if db is None:
            db = PostgresDatabase(
                url,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
            )
            _pool[key] = db
        db.add_ref()
        return db


def reset_sqlite_database_pool() -> None:
    """Test helper: close all pooled databases."""
    with _pool_guard:
        for db in _pool.values():
            try:
                db.conn.close()
                if isinstance(db, PostgresDatabase):
                    db.engine.dispose()
            except Exception:
                pass
        _pool.clear()
