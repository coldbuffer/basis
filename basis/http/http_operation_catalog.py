"""Workspace REST routes exposed as API-token HTTP operation grants."""

from __future__ import annotations

import inspect
from typing import Any

from fastapi import FastAPI
from starlette.routing import Mount

from basis.services.tenancy.admin.api_token_grants import http_operation_grant_for_route

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _route_summary(route: Any) -> str:
    summary = getattr(route, "summary", None)
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    endpoint = getattr(route, "endpoint", None)
    if endpoint is not None:
        doc = inspect.getdoc(endpoint)
        if doc:
            first = doc.strip().splitlines()[0].strip()
            if first:
                return first
    name = getattr(route, "name", None)
    return str(name or "").strip() or "route"


def _route_access(route: Any) -> str:
    methods = getattr(route, "methods", None) or set()
    normalized = {str(m).upper() for m in methods if m}
    if normalized and normalized <= _READ_METHODS:
        return "read"
    return "write"


def _child_routes(route: Any) -> list[Any] | None:
    if isinstance(route, Mount):
        return list(route.routes)
    original = getattr(route, "original_router", None)
    if original is not None:
        return list(original.routes)
    nested = getattr(route, "routes", None)
    if nested is not None and not isinstance(route, Mount):
        try:
            return list(nested)
        except TypeError:
            return None
    return None


def _nested_path_prefix(route: Any, path_prefix: str) -> str:
    if isinstance(route, Mount):
        return f"{path_prefix.rstrip('/')}/{route.path.lstrip('/')}"
    ctx = getattr(route, "include_context", None)
    if ctx is not None:
        extra = getattr(ctx, "prefix", "") or ""
        if extra:
            return f"{path_prefix.rstrip('/')}/{extra.lstrip('/')}".replace("//", "/")
    return path_prefix


def _collect_workspace_http_routes(
    routes: list[Any],
    *,
    path_prefix: str,
    entries: dict[str, dict[str, str]],
) -> None:
    for route in routes:
        children = _child_routes(route)
        if children is not None:
            child_prefix = _nested_path_prefix(route, path_prefix)
            _collect_workspace_http_routes(children, path_prefix=child_prefix, entries=entries)
            continue
        grant = http_operation_grant_for_route(route)
        if grant is None:
            continue
        path = getattr(route, "path", None)
        if not isinstance(path, str):
            continue
        full_path = f"{path_prefix.rstrip('/')}/{path.lstrip('/')}".replace("//", "/")
        if "{workspace_id}" not in full_path:
            continue
        if grant in entries:
            continue
        entries[grant] = {
            "name": grant,
            "description": _route_summary(route),
            "access": _route_access(route),
            "path": full_path,
        }


def workspace_http_operation_entries(app: FastAPI) -> list[dict[str, str]]:
    """Catalog of gated workspace HTTP grants (FastAPI route names)."""
    by_name: dict[str, dict[str, str]] = {}
    _collect_workspace_http_routes(list(app.routes), path_prefix="", entries=by_name)
    return [by_name[key] for key in sorted(by_name)]
