"""Map MCP-style ``{error: ...}`` operation payloads to ``AdminError`` for HTTP."""

from __future__ import annotations

from typing import Any, Literal

from basis.services.errors import AdminError

ConnectorHttpKind = Literal["primitive", "tool", "mapping_sync", "writeback"]


def _codes_for_kind(kind: ConnectorHttpKind) -> tuple[str, str, str]:
    if kind == "mapping_sync":
        return ("mapping_not_found", "connector_sync_failed", "connector_sync_failed")
    if kind == "writeback":
        return ("external_ref_not_found", "writeback_not_permitted", "writeback_propose_failed")
    if kind == "tool":
        return ("connection_not_found", "connector_policy_blocked", "connector_tool_execution_failed")
    return (
        "connection_not_found",
        "connector_policy_blocked",
        "connector_primitive_failed",
    )


def payload_for_http(
    payload: dict[str, Any],
    *,
    kind: ConnectorHttpKind = "primitive",
) -> dict[str, Any]:
    """Return ``payload`` or raise ``AdminError`` when ``payload['error']`` is set."""
    err = payload.get("error")
    if not err or not isinstance(err, str):
        return payload
    not_found_code, policy_code, failure_code = _codes_for_kind(kind)
    lowered = err.lower()
    if kind == "mapping_sync" and err == "mapping not found":
        raise AdminError(404, not_found_code, err)
    if "not found" in lowered:
        raise AdminError(404, not_found_code, err)
    if "permission" in lowered or "policy" in lowered or "blocked" in lowered:
        raise AdminError(403, policy_code, err)
    if kind == "primitive" and ("invalid" in lowered or "required" in lowered):
        raise AdminError(422, "connector_primitive_invalid", err)
    raise AdminError(422, failure_code, err)
