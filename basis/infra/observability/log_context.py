"""Structured logging extras for background work (X-02)."""

from __future__ import annotations

from basis.infra.observability.request_context import current_request_id


def correlation_log_extra(
    *,
    job_id: str | None = None,
    workspace_id: str | None = None,
    version_id: str | None = None,
    projection_revision: int | None = None,
) -> dict[str, str | int]:
    extra: dict[str, str | int] = {}
    rid = current_request_id()
    if rid:
        extra["request_id"] = rid
    if job_id:
        extra["job_id"] = job_id
    if workspace_id:
        extra["workspace_id"] = workspace_id
    if version_id:
        extra["version_id"] = version_id
    if projection_revision is not None:
        extra["projection_revision"] = projection_revision
    return extra
