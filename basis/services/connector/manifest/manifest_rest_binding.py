"""REST binding shorthand: HTTP-oriented ``params`` compiled to adapter retriever/mutation shape."""

from __future__ import annotations

from typing import Any

from basis.services.connector.manifest.manifest_schema import WriteOpLiteral

_DEFAULT_WRITE_METHOD: dict[WriteOpLiteral, str] = {
    "create": "POST",
    "update": "PATCH",
    "upsert": "PUT",
    "delete": "DELETE",
}


def _is_expanded_list_params(params: dict[str, Any]) -> bool:
    return (
        "http_method" in params
        or "request_params" in params
        or "records_field_path" in params
        or "request_headers" in params
    )


def expand_rest_list_params(params: dict[str, Any]) -> dict[str, Any]:
    """Shorthand ``{ path, query?, headers?, paginator?, cursor? }`` → retriever params."""
    if _is_expanded_list_params(params):
        out = dict(params)
        out.setdefault("http_method", "GET")
        out.setdefault("request_params", {})
        out.setdefault("request_headers", {})
        out.setdefault("records_field_path", [])
        return out

    path = params.get("path")
    if not path:
        raise ValueError("REST list binding requires 'path'")

    query = params.get("query", params.get("request_params", {}))
    headers = params.get("headers", params.get("request_headers", {}))
    paginator = params.get("paginator", {"type": "none"})
    cursor = params.get("cursor", params.get("incremental_cursor_param"))

    out: dict[str, Any] = {
        "path": path,
        "http_method": params.get("method", params.get("http_method", "GET")),
        "request_params": query if isinstance(query, dict) else {},
        "request_headers": headers if isinstance(headers, dict) else {},
        "records_field_path": params.get("records_field_path", []),
        "paginator": paginator,
    }
    if params.get("records"):
        out["records_field_path"] = params["records"]
    if params.get("unwrap"):
        out["record_fields_unwrap_path"] = params["unwrap"]
    if cursor:
        out["incremental_cursor_param"] = cursor
    if params.get("body") is not None:
        out["request_body_json"] = params["body"]
    return out


def _is_expanded_write_params(params: dict[str, Any]) -> bool:
    return "path_template" in params or "http_method" in params


def expand_rest_write_params(
    operation: WriteOpLiteral, params: dict[str, Any]
) -> dict[str, Any]:
    """Shorthand ``{ path, method?, body? }`` → mutation params."""
    if _is_expanded_write_params(params):
        out = dict(params)
        out.setdefault("operation", operation)
        out.setdefault("http_method", _DEFAULT_WRITE_METHOD[operation])
        return out

    path = params.get("path") or params.get("path_template")
    if not path:
        raise ValueError(f"REST write binding ({operation}) requires 'path'")

    method = params.get("method", params.get("http_method", _DEFAULT_WRITE_METHOD[operation]))
    body = params.get("body", params.get("body_template", {"patch": "{{patch}}"}))

    return {
        "operation": operation,
        "http_method": method,
        "path_template": path,
        "request_params": params.get("query", params.get("request_params", {})),
        "request_headers": params.get("headers", params.get("request_headers", {})),
        "body_template": body,
    }


def compact_rest_list_params(retriever_params: dict[str, Any]) -> dict[str, Any]:
    """Expanded retriever params → shorthand for authoring (drops empty defaults)."""
    out: dict[str, Any] = {"path": retriever_params.get("path", "")}
    rp = retriever_params.get("request_params") or {}
    if rp:
        out["query"] = rp
    rh = retriever_params.get("request_headers") or {}
    if rh:
        out["headers"] = rh
    paginator = retriever_params.get("paginator")
    if paginator and paginator != {"type": "none"}:
        out["paginator"] = paginator
    inc = retriever_params.get("incremental_cursor_param")
    if inc:
        out["cursor"] = inc
    rfp = retriever_params.get("records_field_path")
    if rfp:
        out["records"] = rfp
    return out


def compact_rest_write_params(mutation_params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pt = mutation_params.get("path_template") or mutation_params.get("path")
    if pt:
        out["path"] = pt
    method = mutation_params.get("http_method")
    op = mutation_params.get("operation", "update")
    default_method = _DEFAULT_WRITE_METHOD.get(op, "PATCH")
    if method and method != default_method:
        out["method"] = method
    rp = mutation_params.get("request_params") or {}
    if rp:
        out["query"] = rp
    rh = mutation_params.get("request_headers") or {}
    if rh:
        out["headers"] = rh
    body = mutation_params.get("body_template")
    if body and body != {"patch": "{{patch}}"}:
        out["body"] = body
    elif body:
        out["body"] = body
    return out
