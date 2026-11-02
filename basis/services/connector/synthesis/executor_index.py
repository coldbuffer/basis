"""Optional static map: AnyConnect action id → REST invoke wire (P4 build artifact)."""

from __future__ import annotations

import json
from typing import Any

from basis.services.connector.adapters.mail.actions import is_mail_action
from basis.services.connector.adapters.mail.credentials import MAIL_CREDENTIAL_READERS
from basis.services.connector.synthesis.paths import executor_index_path


def _load_index() -> dict[str, Any]:
    path = executor_index_path()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def invoke_wire_for_action(service: str, action_id: str) -> dict[str, Any] | None:
    """Return REST wire ``{"method", "path"}`` or mail ``{"adapter": "mail", "action"}``."""
    mail_wire = _mail_invoke_wire(service, action_id)
    if mail_wire is not None:
        return mail_wire
    index = _load_index()
    by_service = index.get(service)
    if isinstance(by_service, dict):
        wire = by_service.get(action_id) or by_service.get(action_id.split(".")[-1])
        if isinstance(wire, dict):
            method = str(wire.get("method") or "POST").upper()
            path = str(wire.get("path") or "")
            if path:
                return {"method": method, "path": path}
    if service == "slack":
        from basis.services.connector.synthesis.slack_invoke_map import slack_invoke_wire

        return slack_invoke_wire(action_id)
    if service == "gitlab":
        from basis.services.connector.synthesis.gitlab_invoke_map import gitlab_invoke_wire

        return gitlab_invoke_wire(action_id)
    if service == "jira":
        from basis.services.connector.synthesis.jira_invoke_map import jira_invoke_wire

        return jira_invoke_wire(action_id)
    return None


def _mail_invoke_wire(service: str, action_id: str) -> dict[str, Any] | None:
    if service not in MAIL_CREDENTIAL_READERS:
        return None
    short = action_id.split(".")[-1]
    if not is_mail_action(short):
        return None
    return {"adapter": "mail", "action": short}
