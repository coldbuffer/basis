"""Connector manifest tool execution use case."""

from __future__ import annotations

from typing import Any

from basis.services.connector import authz
from basis.services.kernel import WorkspaceCoreContext


def execute_tool(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    service = str(args.get("service") or "").strip()
    tool_id = str(args.get("tool_id") or "").strip()
    connection_scope = str(args.get("connection_scope") or "workspace").strip() or "workspace"
    subject_id_raw = args.get("subject_id")
    subject_id = (
        str(subject_id_raw).strip()
        if subject_id_raw is not None and str(subject_id_raw).strip()
        else None
    )
    arguments = args.get("arguments")
    if not service or not tool_id:
        return {"error": "service and tool_id are required"}
    if arguments is not None and not isinstance(arguments, dict):
        return {"error": "arguments must be an object"}
    authz.require_workspace_editor(ctx)
    runtime = ctx.knowledge.connector_runtime()
    try:
        return runtime.execute_tool(
            ctx.workspace.id,
            service,
            tool_id,
            connection_scope=connection_scope,
            subject_id=subject_id,
            arguments=arguments or {},
        )
    except PermissionError as exc:
        return {"error": str(exc)}
    except (LookupError, ValueError) as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": str(exc)}

