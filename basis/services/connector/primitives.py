"""BOCP primitive invoke use case."""

from __future__ import annotations

from typing import Any

from basis.services.connector import authz
from basis.services.kernel import WorkspaceCoreContext
from basis.services.connector.primitive_invoke import execute_connector_primitive


def invoke(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    service = str(args.get("service") or "").strip()
    action_id = str(args.get("action_id") or "").strip()
    primitive = str(args.get("primitive") or "").strip().lower()
    connection_scope = str(args.get("connection_scope") or "workspace").strip() or "workspace"
    subject_id_raw = args.get("subject_id")
    subject_id = (
        str(subject_id_raw).strip()
        if subject_id_raw is not None and str(subject_id_raw).strip()
        else None
    )
    operation = str(args.get("operation") or "").strip() or None
    external_table = str(args.get("external_table") or "").strip() or None
    external_id = args.get("external_id")
    changes = args.get("changes")
    action_params = args.get("action_params")
    arguments = args.get("arguments")
    if not service or not action_id or not primitive:
        return {"error": "service, action_id, and primitive are required"}
    if action_params is not None and not isinstance(action_params, dict):
        return {"error": "action_params must be an object"}
    if changes is not None and not isinstance(changes, dict):
        return {"error": "changes must be an object"}
    if arguments is not None and not isinstance(arguments, dict):
        return {"error": "arguments must be an object"}
    limit = int(args.get("limit") or 500)
    cursor_watermark = args.get("cursor_watermark")
    primary_key_column = str(args.get("primary_key_column") or "id")
    cursor_column = args.get("cursor_column")
    cursor_column_str = str(cursor_column).strip() if cursor_column else None

    read_primitive = primitive in ("discover", "list")
    if read_primitive:
        authz.require_workspace_viewer(ctx)
    else:
        authz.require_workspace_editor(ctx)

    runtime = ctx.knowledge.connector_runtime()
    try:
        return execute_connector_primitive(
            runtime,
            ctx.workspace.id,
            service,
            action_id=action_id,
            primitive=primitive,
            connection_scope=connection_scope,
            subject_id=subject_id,
            operation=operation,
            external_table=external_table,
            external_id=external_id,
            changes=changes,
            action_params=action_params,
            limit=limit,
            cursor_watermark=cursor_watermark,
            arguments=arguments,
            primary_key_column=primary_key_column,
            cursor_column=cursor_column_str,
        )
    except PermissionError as exc:
        return {"error": str(exc)}
    except (LookupError, ValueError) as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": str(exc)}

