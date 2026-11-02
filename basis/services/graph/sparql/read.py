"""Read-only SPARQL over an in-memory rdflib graph projection."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import rdflib

_ALLOWED_QUERY_TYPES = re.compile(
    r"^(SELECT|ASK|CONSTRUCT|DESCRIBE)\b",
    re.IGNORECASE,
)
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|DELETE|DROP|LOAD|CLEAR|CREATE|COPY|MOVE|ADD)\b",
    re.IGNORECASE,
)
_COMMENT_LINE = re.compile(r"(?:^|(?<=\s))#[^\n]*", re.MULTILINE)
_PREFIX_DECL = re.compile(
    r"^[ \t]*(?:PREFIX[ \t]+\S+|BASE)[ \t]*<[^>\r\n]*>[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)

_SPARQL_MAX_ROWS = 5_000
_SPARQL_TIMEOUT_S = 30
SPARQL_TIMEOUT_S = _SPARQL_TIMEOUT_S
_SPARQL_MAX_CONCURRENT = 4
_SPARQL_MAX_GRAPH_NODES = 50_000
_SPARQL_MAX_QUERY_LEN = 10_000

NS = rdflib.Namespace("http://semantica.local/entity/")
PROP = rdflib.Namespace("http://semantica.local/prop/")


def _is_read_only_query(query: str) -> bool:
    cleaned = _COMMENT_LINE.sub("", query)
    cleaned = _PREFIX_DECL.sub("", cleaned)
    cleaned = cleaned.strip()
    if not _ALLOWED_QUERY_TYPES.match(cleaned):
        return False
    if _FORBIDDEN_KEYWORDS.search(cleaned):
        return False
    return True


def _error_response(
    message: str,
    *,
    error_line: int | None = None,
    error_column: int | None = None,
) -> dict[str, Any]:
    return {
        "columns": [],
        "rows": [],
        "total": 0,
        "truncated": False,
        "error": message,
        "error_line": error_line,
        "error_column": error_column,
    }


def _build_rdflib_graph(session: Any) -> rdflib.Graph:
    graph = rdflib.Graph()
    graph.bind("ent", NS)
    graph.bind("prop", PROP)

    nodes, _total_nodes = session.get_nodes(skip=0, limit=_SPARQL_MAX_GRAPH_NODES + 1)
    if len(nodes) > _SPARQL_MAX_GRAPH_NODES:
        raise ValueError(
            f"Graph has more than {_SPARQL_MAX_GRAPH_NODES:,} nodes. "
            f"SPARQL queries are limited to graphs with at most "
            f"{_SPARQL_MAX_GRAPH_NODES:,} nodes to prevent excessive "
            f"memory usage. Use the REST API for large graph operations."
        )

    edges, _ = session.get_edges(skip=0, limit=_SPARQL_MAX_GRAPH_NODES + 1)
    if len(edges) > _SPARQL_MAX_GRAPH_NODES:
        raise ValueError(
            f"Graph has more than {_SPARQL_MAX_GRAPH_NODES:,} edges. "
            f"SPARQL queries are limited to graphs with at most "
            f"{_SPARQL_MAX_GRAPH_NODES:,} edges to prevent excessive "
            f"memory usage. Use the REST API for large graph operations."
        )

    for node in nodes:
        subject = NS[str(node.get("id", ""))]
        node_type = node.get("type", "Entity")
        graph.add((subject, rdflib.RDF.type, NS[node_type]))

        content = node.get("content", "")
        if content:
            graph.add((subject, rdflib.RDFS.label, rdflib.Literal(content)))

        for key, value in node.get("properties", {}).items():
            if key in {"content", "valid_from", "valid_until"}:
                continue
            graph.add((subject, PROP[key], rdflib.Literal(value)))

    for edge in edges:
        source = NS[str(edge.get("source", ""))]
        target = NS[str(edge.get("target", ""))]
        relationship = edge.get("type", "relatedTo")
        graph.add((source, PROP[relationship], target))

    return graph


def _cap_rows(
    items: Any,
    row_builder: Callable[[Any], dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    truncated = False
    for item in items:
        if len(rows) >= _SPARQL_MAX_ROWS:
            truncated = True
            break
        rows.append(row_builder(item))
    return rows, truncated


def _serialize_query_results(query_results: Any) -> dict[str, Any]:
    query_type: str = query_results.type

    if query_type == "ASK":
        columns = ["result"]
        rows = [{"result": "true" if query_results.askAnswer else "false"}]
        truncated = False
    elif query_type in ("CONSTRUCT", "DESCRIBE"):
        columns = ["subject", "predicate", "object"]
        rows, truncated = _cap_rows(
            query_results,
            lambda triple: {
                "subject": str(triple[0]),
                "predicate": str(triple[1]),
                "object": str(triple[2]),
            },
        )
    else:
        columns = [str(var) for var in (query_results.vars or [])]
        rows, truncated = _cap_rows(
            query_results,
            lambda row: {
                column: (str(row[index]) if row[index] is not None else None)
                for index, column in enumerate(columns)
            },
        )

    return {
        "columns": columns,
        "rows": rows,
        "total": len(rows),
        "truncated": truncated,
        "error": None,
        "error_line": None,
        "error_column": None,
    }


def run_sparql_on_graph(graph: rdflib.Graph, query: str) -> dict[str, Any]:
    try:
        query_results = graph.query(query)
    except Exception as exc:
        error = str(exc)
        line_match = re.search(r"line[\s:]+(\d+)", error, re.IGNORECASE)
        column_match = re.search(r"col(?:umn)?[\s:]+(\d+)", error, re.IGNORECASE)
        return _error_response(
            error,
            error_line=int(line_match.group(1)) if line_match else None,
            error_column=int(column_match.group(1)) if column_match else None,
        )
    return _serialize_query_results(query_results)


def sparql_query_preflight(query: str) -> dict[str, Any] | None:
    """Return an error payload dict, or None if the query may proceed."""
    if len(query) > _SPARQL_MAX_QUERY_LEN:
        return _error_response(
            f"Query exceeds the maximum allowed length of "
            f"{_SPARQL_MAX_QUERY_LEN:,} characters "
            f"({len(query):,} received). "
            f"Please shorten your query."
        )
    if not _is_read_only_query(query):
        return _error_response(
            "Only SELECT, ASK, CONSTRUCT, and DESCRIBE queries are permitted."
        )
    return None


def build_sparql_graph(session: Any) -> rdflib.Graph:
    return _build_rdflib_graph(session)


def sparql_timeout_response() -> dict[str, Any]:
    return _error_response(f"Query timed out after {SPARQL_TIMEOUT_S} seconds.")


def sparql_error_response(message: str) -> dict[str, Any]:
    return _error_response(message)
