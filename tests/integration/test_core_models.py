"""Pydantic coercion for core operation arguments."""

import pytest
from pydantic import ValidationError

from basis.application.tool_catalog import coerce_operation_args, run


def test_coerce_search_chunks_requires_query() -> None:
    with pytest.raises(ValidationError):
        coerce_operation_args("search_chunks", {"limit": 5})


def test_run_rejects_empty_query_graph_search_query() -> None:
    class _Workspace:
        id = "ws1"

    class _Ctx:
        workspace = _Workspace()
        api_token = None

    payload = run(_Ctx(), "query_graph", {"mode": "search", "query": ""})  # type: ignore[arg-type]
    assert "error" in payload
