"""SQLAlchemy 2.0 relational database adapter for BOCP (`postgres`, `mysql`, `sqlite`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    inspect,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.types import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    JSON,
    Numeric,
)

from basis.domain.connector.auth_vault import StoredConnection
from basis.domain.connector.manifest_schema import StreamFieldSpec


@dataclass
class DiscoveredTableSchema:
    table_name: str
    schema_name: str | None
    primary_key: list[str]
    fields: list[StreamFieldSpec] = field(default_factory=list)


@dataclass
class SqlBatchResult:
    records: list[dict[str, Any]]
    next_cursor_value: Any | None = None
    has_more: bool = False


def build_sqlalchemy_dsn(connection: StoredConnection) -> str:
    """Build a SQLAlchemy 2.0 connection URL from a BOCP StoredConnection."""
    cfg = connection.connection_config
    creds = connection.credentials

    # Allow explicit dsn override for testing (e.g. sqlite:///...)
    if cfg.get("dsn"):
        return str(cfg["dsn"])

    service = connection.service.lower()
    host = str(cfg.get("host") or "localhost")
    database = str(cfg.get("database") or "")
    username = quote_plus(str(creds.get("username") or ""))
    password = quote_plus(str(creds.get("password") or ""))

    if service == "postgres":
        port = int(cfg.get("port") or 5432)
        return f"postgresql+psycopg://{username}:{password}@{host}:{port}/{database}"
    if service == "mysql":
        port = int(cfg.get("port") or 3306)
        driver = str(cfg.get("driver") or "pymysql")
        return f"mysql+{driver}://{username}:{password}@{host}:{port}/{database}"
    if service == "sqlite":
        return f"sqlite:///{database}"

    raise ValueError(f"Unsupported SQLAlchemy database service: {service}")


def _map_sa_type(col_type: Any) -> str:
    if isinstance(col_type, Boolean):
        return "boolean"
    if isinstance(col_type, Integer):
        return "integer"
    if isinstance(col_type, (Float, Numeric)):
        return "number"
    if isinstance(col_type, DateTime):
        return "datetime"
    if isinstance(col_type, Date):
        return "date"
    if isinstance(col_type, JSON):
        return "json"
    return "string"


def split_schema_and_table(
    external_table: str, default_schema: str | None = None
) -> tuple[str | None, str]:
    if "." in external_table:
        schema_part, table_part = external_table.split(".", 1)
        return schema_part, table_part
    return default_schema, external_table


class SqlAlchemyStreamAdapter:
    """Executes CHECK, DISCOVER, READ, and MUTATE against relational databases via SQLAlchemy 2.0."""

    def __init__(self, engine: Engine, *, default_schema: str | None = None) -> None:
        self._engine = engine
        self._default_schema = default_schema

    @classmethod
    def from_connection(cls, connection: StoredConnection) -> SqlAlchemyStreamAdapter:
        dsn = build_sqlalchemy_dsn(connection)
        engine = create_engine(dsn, pool_pre_ping=True)
        default_schema = connection.connection_config.get("schema")
        if connection.service == "sqlite" or dsn.startswith("sqlite"):
            default_schema = None
        return cls(
            engine,
            default_schema=str(default_schema) if default_schema else None,
        )

    def close(self) -> None:
        self._engine.dispose()

    def check_connection(self) -> dict[str, Any]:
        """Run a lightweight connectivity check (`CHECK` primitive)."""
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            dialect = self._engine.dialect.name
            return {
                "ok": True,
                "dialect": dialect,
                "database": self._engine.url.database or "default",
            }

    def list_tables(self, *, schema: str | None = None) -> list[str]:
        """List available tables/views in the target schema."""
        target_schema = schema if schema is not None else self._default_schema
        insp = inspect(self._engine)
        names = insp.get_table_names(schema=target_schema)
        if target_schema:
            return [f"{target_schema}.{n}" for n in sorted(names)]
        return sorted(names)

    def discover_table_schema(self, external_table: str) -> DiscoveredTableSchema:
        """Introspect columns, primary keys, and foreign keys (`DISCOVER` primitive)."""
        schema_name, table_name = split_schema_and_table(
            external_table, self._default_schema
        )
        insp = inspect(self._engine)
        pk_constraint = insp.get_pk_constraint(table_name, schema=schema_name) or {}
        pk_cols: list[str] = list(pk_constraint.get("constrained_columns") or [])

        fks = insp.get_foreign_keys(table_name, schema=schema_name) or []
        fk_by_col: dict[str, str] = {}
        for fk in fks:
            constrained = fk.get("constrained_columns") or []
            referred_table = fk.get("referred_table")
            referred_schema = fk.get("referred_schema")
            if len(constrained) == 1 and referred_table:
                target = (
                    f"{referred_schema}.{referred_table}"
                    if referred_schema
                    else str(referred_table)
                )
                fk_by_col[str(constrained[0])] = target

        raw_cols = insp.get_columns(table_name, schema=schema_name)
        fields: list[StreamFieldSpec] = []
        for col in raw_cols:
            col_name = str(col["name"])
            fields.append(
                StreamFieldSpec(
                    name=col_name,
                    data_type=_map_sa_type(col.get("type")),  # type: ignore[arg-type]
                    nullable=bool(col.get("nullable", True)),
                    primary_key=col_name in pk_cols,
                    fk_target_stream=fk_by_col.get(col_name),
                )
            )
        return DiscoveredTableSchema(
            table_name=table_name,
            schema_name=schema_name,
            primary_key=pk_cols,
            fields=fields,
        )

    @staticmethod
    def _coerce_cursor_watermark(column: Any, value: Any) -> Any:
        """Align checkpoint watermarks with reflected column types (e.g. PG timestamptz)."""
        if value is None:
            return None
        col_type = getattr(column, "type", None)
        if isinstance(col_type, (DateTime, Date)):
            if isinstance(value, datetime):
                return value
            if isinstance(value, date) and not isinstance(value, datetime):
                return value
            if isinstance(value, str):
                text_value = value.strip()
                if text_value.endswith("Z"):
                    text_value = f"{text_value[:-1]}+00:00"
                parsed = datetime.fromisoformat(text_value)
                if isinstance(col_type, DateTime):
                    return parsed
                if isinstance(col_type, Date):
                    return parsed.date()
                return parsed
        return value

    def _reflect_table(self, external_table: str) -> Table:
        schema_name, table_name = split_schema_and_table(
            external_table, self._default_schema
        )
        metadata = MetaData()
        return Table(
            table_name,
            metadata,
            schema=schema_name,
            autoload_with=self._engine,
        )

    def read_records(
        self,
        external_table: str,
        *,
        primary_key_column: str,
        cursor_column: str | None = None,
        cursor_watermark: Any | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> SqlBatchResult:
        """Read rows with parameterized SQLAlchemy Core expressions (`READ` primitive)."""
        table = self._reflect_table(external_table)
        if primary_key_column not in table.c:
            raise ValueError(
                f"Primary key column '{primary_key_column}' not found in {external_table}"
            )
        pk_col = table.c[primary_key_column]

        stmt = select(table)
        if cursor_column:
            if cursor_column not in table.c:
                raise ValueError(
                    f"Cursor column '{cursor_column}' not found in {external_table}"
                )
            cur_col = table.c[cursor_column]
            if cursor_watermark is not None:
                bound = self._coerce_cursor_watermark(cur_col, cursor_watermark)
                stmt = stmt.where(cur_col >= bound)
            stmt = stmt.order_by(cur_col.asc(), pk_col.asc())
        else:
            stmt = stmt.order_by(pk_col.asc())

        stmt = stmt.limit(limit + 1).offset(offset)

        with self._engine.connect() as conn:
            rows = [dict(r._mapping) for r in conn.execute(stmt).fetchall()]

        has_more = len(rows) > limit
        records = rows[:limit]
        next_cursor = None
        if records and cursor_column:
            next_cursor = records[-1].get(cursor_column)

        return SqlBatchResult(
            records=records,
            next_cursor_value=next_cursor,
            has_more=has_more,
        )

    def fetch_single_record(
        self,
        external_table: str,
        *,
        primary_key_column: str,
        external_pk: Any,
    ) -> dict[str, Any] | None:
        """Fetch a single row by primary key for pre-writeback optimistic concurrency checks."""
        table = self._reflect_table(external_table)
        pk_col = table.c[primary_key_column]
        stmt = select(table).where(pk_col == external_pk).limit(1)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).fetchone()
            return dict(row._mapping) if row is not None else None

    def mutate_record(
        self,
        external_table: str,
        *,
        operation: str,
        primary_key_column: str,
        external_pk: Any,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a parameterized UPDATE or INSERT (`MUTATE` primitive) and return the updated row."""
        table = self._reflect_table(external_table)
        pk_col = table.c[primary_key_column]

        valid_values: dict[str, Any] = {}
        for col_name, val in changes.items():
            if col_name not in table.c:
                raise ValueError(
                    f"Column '{col_name}' does not exist on table {external_table}"
                )
            valid_values[col_name] = val

        with self._engine.begin() as conn:
            if operation == "create":
                insert_vals = {primary_key_column: external_pk, **valid_values}
                conn.execute(insert(table).values(**insert_vals))
            elif operation in ("update", "upsert"):
                res = conn.execute(
                    update(table).where(pk_col == external_pk).values(**valid_values)
                )
                if (res.rowcount or 0) == 0 and operation == "upsert":
                    insert_vals = {primary_key_column: external_pk, **valid_values}
                    conn.execute(insert(table).values(**insert_vals))
                elif (res.rowcount or 0) == 0:
                    raise LookupError(
                        f"Target row {primary_key_column}={external_pk} not found in {external_table}"
                    )
            else:
                raise ValueError(f"Unsupported SQL mutation operation: {operation}")

            updated = conn.execute(
                select(table).where(pk_col == external_pk).limit(1)
            ).fetchone()
            return dict(updated._mapping) if updated is not None else {}
