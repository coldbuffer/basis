"""Connection scope for workspace-shared vs per end-user (embed) vault rows."""

from __future__ import annotations

from typing import Literal

ConnectionScope = Literal["workspace", "end_user"]

SCOPE_WORKSPACE: ConnectionScope = "workspace"
SCOPE_END_USER: ConnectionScope = "end_user"

# SQLite PK uses TEXT; workspace rows use empty subject_id.
WORKSPACE_SUBJECT_ID = ""


def normalize_connection_scope(value: str | None) -> ConnectionScope:
    raw = (value or SCOPE_WORKSPACE).strip().lower()
    if raw in (SCOPE_WORKSPACE, SCOPE_END_USER):
        return raw
    raise ValueError(f"Invalid connection_scope: {value!r}")


def normalize_subject_id(value: str | None, *, scope: ConnectionScope) -> str:
    if scope == SCOPE_WORKSPACE:
        return WORKSPACE_SUBJECT_ID
    subject = (value or "").strip()
    if not subject:
        raise ValueError("subject_id is required when connection_scope is end_user")
    return subject


class WorkspaceSharedBlocksEndUserError(ValueError):
    """Raised when end_user vault rows are not allowed because the service uses workspace scope."""


def assert_end_user_allowed_for_service(
    *,
    scope: ConnectionScope,
    has_workspace_connection: bool,
    service: str,
) -> None:
    if scope == SCOPE_END_USER and has_workspace_connection:
        raise WorkspaceSharedBlocksEndUserError(
            f"Service '{service}' already has a workspace-shared connection; "
            "end_user authorizations are not allowed for the same provider."
        )
