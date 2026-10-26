"""Pydantic models for named tool arguments and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from basis.application.schema_base import ExtraAllowedModel


class ListProcessingJobsInput(ExtraAllowedModel):
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"] | None = None
    limit: int = Field(default=100, ge=1, le=200)


class ListProcessingJobsResponse(ExtraAllowedModel):
    jobs: list[Any] = Field(default_factory=list)


class ResetWorkspaceInput(ExtraAllowedModel):
    preview: bool = False
    async_mode: bool = Field(
        default=True,
        alias="async",
        description="When true (default), enqueue workspace_reset and poll job_id via list_processing_jobs.",
    )
    job_id: str | None = Field(
        default=None,
        description="Internal: execute a queued workspace_reset job.",
    )
    confirmation: str | None = Field(
        default=None,
        description="Workspace display name; required when preview is false.",
    )
    scopes: list[str] | None = Field(
        default=None,
        description="Reset scopes: knowledge, graph, connectors, reasoning, governance. Default omits governance.",
    )


class ResetWorkspacePreviewResponse(ExtraAllowedModel):
    preview: bool = True
    workspace_id: str
    workspace_name: str
    counts: dict[str, int] = Field(default_factory=dict)
    scopes: list[str] = Field(default_factory=list)
    default_scopes: list[str] = Field(default_factory=list)
    available_scopes: list[str] = Field(default_factory=list)
    export_pack_path: str | None = None


TOOL_INPUT_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "list_processing_jobs": ListProcessingJobsInput,
    "reset_workspace": ResetWorkspaceInput,
}

TOOL_RESPONSE_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "list_processing_jobs": ListProcessingJobsResponse,
    "reset_workspace": ResetWorkspacePreviewResponse,
}
