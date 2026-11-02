"""Workspace API token operation grants (MCP tool names vs HTTP route names)."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from typing import Any

from basis.services.tenancy.admin.admin_types import ApiTokenRecord


@dataclass(frozen=True)
class ApiTokenOperationGrants:
    mcp: frozenset[str] | None
    http: frozenset[str] | None


def _clean_operation_ids(values: Any) -> frozenset[str] | None:
    if not isinstance(values, list):
        return None
    cleaned = {str(item).strip() for item in values if str(item).strip()}
    if not cleaned:
        return None
    return frozenset(cleaned)


def parse_operation_grants_json(raw: str | None) -> ApiTokenOperationGrants:
    """``None`` on both sides = unrestricted (legacy tokens)."""
    if raw is None or not str(raw).strip():
        return ApiTokenOperationGrants(mcp=None, http=None)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ApiTokenOperationGrants(mcp=None, http=None)
    if isinstance(data, list):
        legacy = _clean_operation_ids(data)
        return ApiTokenOperationGrants(mcp=legacy, http=legacy)
    if isinstance(data, dict):
        return ApiTokenOperationGrants(
            mcp=_clean_operation_ids(data.get("mcp")),
            http=_clean_operation_ids(data.get("http")),
        )
    return ApiTokenOperationGrants(mcp=None, http=None)


def encode_operation_grants_json(
    *,
    mcp_allowed_operations: list[str] | None,
    http_allowed_operations: list[str] | None,
) -> str | None:
    mcp = _clean_operation_ids(mcp_allowed_operations)
    http = _clean_operation_ids(http_allowed_operations)
    if mcp is None and http is None:
        return None
    payload: dict[str, list[str]] = {}
    if mcp is not None:
        payload["mcp"] = sorted(mcp)
    if http is not None:
        payload["http"] = sorted(http)
    return json.dumps(payload, ensure_ascii=False)


def _allows_in_set(allowed: frozenset[str] | None, operation: str) -> bool:
    if allowed is None:
        return True
    op = operation.strip()
    if not op:
        return False
    if op in allowed:
        return True
    for pattern in allowed:
        if "*" in pattern and fnmatch.fnmatchcase(op, pattern):
            return True
    return False


def token_allows_mcp_operation(record: ApiTokenRecord, operation: str) -> bool:
    return _allows_in_set(record.mcp_allowed_operations, operation)


def token_allows_http_operation(record: ApiTokenRecord, operation: str) -> bool:
    return _allows_in_set(record.http_allowed_operations, operation)


def http_operation_grant_for_route(route: Any) -> str | None:
    """Resolve HTTP grant id (FastAPI route name), or ``None`` if not gated."""
    name = getattr(route, "name", None)
    if not isinstance(name, str) or not name.strip():
        return None
    if name in ("mcp_integration_info", "mcp_jsonrpc"):
        return None
    return name.strip()


def assert_api_token_http_operation(request: Any, record: ApiTokenRecord) -> None:
    from fastapi import HTTPException

    if record.http_allowed_operations is None:
        return
    route = request.scope.get("route")
    if route is None:
        return
    grant = http_operation_grant_for_route(route)
    if grant is None:
        return
    if not token_allows_http_operation(record, grant):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "forbidden",
                "message": f"令牌未授权 OpenAPI 操作：{grant}",
            },
        )
