"""Turn a live SQL catalog connector into a JSON snapshot."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from basis.services.sql_catalog.engines.base import SQLDatabase
from basis.services.sql_catalog.table_filter import TableFilter, apply, filter_frame

_QUERY_LIMIT = 500


def _records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def collect_catalog(connector: SQLDatabase, table_filter: TableFilter) -> dict[str, Any]:
    """Read schema metadata and apply the connection's table allow/deny filter."""
    tables, columns, views = apply(
        connector.get_tables(),
        connector.get_columns(),
        connector.get_views(),
        table_filter,
    )
    primary_keys = filter_frame(connector.get_pks(), table_filter)
    foreign_keys = filter_frame(connector.get_fks(), table_filter)
    queries = connector.get_queries()
    if queries is not None and not queries.empty and len(queries) > _QUERY_LIMIT:
        queries = queries.head(_QUERY_LIMIT)
    return {
        "database_name": connector.database_name,
        "dialect": connector.dialect,
        "tables": _records(tables),
        "columns": _records(columns),
        "views": _records(views),
        "primary_keys": _records(primary_keys),
        "foreign_keys": _records(foreign_keys),
        "queries": _records(queries),
    }
