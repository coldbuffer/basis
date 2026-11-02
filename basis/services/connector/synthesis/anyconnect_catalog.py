"""OpenConnector / connector ``catalog/apps/{service}.json`` → BOCP procedures (P3)."""

from __future__ import annotations

import json
from typing import Any

from basis.services.connector.manifest.manifest_actions import (
    procedure_action_from_mail_tool,
    procedure_action_from_tool,
)
from basis.services.connector.manifest.manifest_schema import ProcedureActionSpec, ToolAnnotationsSpec, ToolSpec
from basis.services.connector.synthesis.executor_index import invoke_wire_for_action
from basis.services.connector.synthesis.paths import connector_catalog_dir


def load_connector_app(service: str) -> dict[str, Any] | None:
    root = connector_catalog_dir()
    if root is None:
        return None
    for name in (f"{service}.json", f"{service.replace('_', '-')}.json"):
        path = root / name
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    return None


def _short_action_name(action_id: str) -> str:
    if "." in action_id:
        return action_id.split(".")[-1]
    return action_id


def procedures_from_anyconnect_app(
    app: dict[str, Any],
    *,
    service: str,
) -> list[ProcedureActionSpec]:
    procedures: list[ProcedureActionSpec] = []
    for item in app.get("actions") or []:
        if not isinstance(item, dict):
            continue
        action_id = str(item.get("id") or item.get("name") or "").strip()
        if not action_id:
            continue
        wire = invoke_wire_for_action(service, action_id)
        if not wire:
            continue
        if wire.get("adapter") == "mail":
            mail_action = str(wire.get("action") or "").strip()
            if not mail_action:
                continue
            input_schema = item.get("inputSchema") or item.get("input_schema") or {}
            output_schema = item.get("outputSchema") or item.get("output_schema") or {}
            if not isinstance(input_schema, dict):
                input_schema = {}
            if not isinstance(output_schema, dict):
                output_schema = {}
            scopes = item.get("requiredScopes") or item.get("required_scopes") or []
            if not isinstance(scopes, list):
                scopes = []
            name = _short_action_name(action_id)
            tool = ToolSpec(
                id=action_id,
                name=name,
                description=str(item.get("description") or ""),
                required_scopes=[str(s) for s in scopes],
                annotations=ToolAnnotationsSpec(
                    read_only_hint=name in ("list_folders", "search_emails", "get_email", "get_folder_status"),
                    destructive_hint=name in ("delete_email",),
                    idempotent_hint=False,
                ),
                input_schema=input_schema,
                output_schema=output_schema,
            )
            procedures.append(procedure_action_from_mail_tool(tool, mail_action=mail_action))
            continue
        if not str(wire.get("path") or "").strip():
            continue
        method = str(wire.get("method") or "POST").upper()
        path = str(wire["path"])
        input_schema = item.get("inputSchema") or item.get("input_schema") or {}
        output_schema = item.get("outputSchema") or item.get("output_schema") or {}
        if not isinstance(input_schema, dict):
            input_schema = {}
        if not isinstance(output_schema, dict):
            output_schema = {}
        scopes = item.get("requiredScopes") or item.get("required_scopes") or []
        if not isinstance(scopes, list):
            scopes = []
        name = _short_action_name(action_id)
        body_encoding = "json"
        if service == "slack" and method != "GET":
            body_encoding = "form"
        tool = ToolSpec(
            id=action_id,
            name=name,
            description=str(item.get("description") or ""),
            required_scopes=[str(s) for s in scopes],
            annotations=ToolAnnotationsSpec(
                read_only_hint=method == "GET",
                destructive_hint=False,
                idempotent_hint=method == "GET",
            ),
            input_schema=input_schema,
            output_schema=output_schema,
            http_method=method,
            path_template=path,
            body_encoding=body_encoding,
        )
        procedures.append(procedure_action_from_tool(tool))
    return procedures


def anyconnect_app_metadata(app: dict[str, Any]) -> dict[str, Any]:
    display = app.get("displayName") or app.get("display_name") or app.get("name")
    description = app.get("description") or ""
    categories = app.get("categories") or app.get("category") or []
    if isinstance(categories, str):
        categories = [categories]
    homepage = app.get("homepageUrl") or app.get("homepage_url")
    docs = app.get("docsUrl") or app.get("docs_url")
    return {
        "display_name": str(display or "").strip() or None,
        "description": str(description).strip() or None,
        "categories": [str(c) for c in categories] if isinstance(categories, list) else [],
        "homepage_url": homepage if isinstance(homepage, str) else None,
        "docs_url": docs if isinstance(docs, str) else None,
    }


def load_connector_catalog_procedures(
    service: str,
) -> tuple[dict[str, Any], list[ProcedureActionSpec]] | None:
    app = load_connector_app(service)
    if app is None:
        return None
    meta = anyconnect_app_metadata(app)
    return meta, procedures_from_anyconnect_app(app, service=service)


def load_anyconnect_procedures(
    service: str,
) -> tuple[dict[str, Any], list[ProcedureActionSpec]] | None:
    """Alias for :func:`load_connector_catalog_procedures`."""
    return load_connector_catalog_procedures(service)
