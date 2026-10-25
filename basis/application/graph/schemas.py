"""Pydantic models for named tool arguments and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from basis.application.schema_base import ExtraAllowedModel


class PathsInput(ExtraAllowedModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    algorithm: Literal["bfs", "dijkstra"] = "bfs"
    directed: bool = True


class PathsResponse(ExtraAllowedModel):
    pass


TOOL_INPUT_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "paths": PathsInput,
}

TOOL_RESPONSE_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "paths": PathsResponse,
}
