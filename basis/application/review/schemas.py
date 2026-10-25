"""Pydantic models for named tool arguments and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from basis.application.schema_base import ExtraAllowedModel

class ApproveReviewItemResponse(ExtraAllowedModel):
    item: dict[str, Any]
    decision_id: str | None = None

class GetReviewItemInput(ExtraAllowedModel):
    item_id: str = Field(min_length=1)

class GetReviewItemResponse(ExtraAllowedModel):
    item: dict[str, Any]

class ListReviewItemsInput(ExtraAllowedModel):
    status: str | None = None
    kind: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

class ListReviewItemsResponse(ExtraAllowedModel):
    items: list[Any] = Field(default_factory=list)
    offset: int = 0
    limit: int = 50
    total: int = 0
    has_more: bool = False

class ResolveReviewItemInput(ExtraAllowedModel):
    item_id: str = Field(min_length=1)
    rationale: str | None = None
    primary_id: str | None = None

TOOL_INPUT_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "approve_review_item": ResolveReviewItemInput,
    "get_review_item": GetReviewItemInput,
    "list_review_items": ListReviewItemsInput,
    "reject_review_item": ResolveReviewItemInput,
}

TOOL_RESPONSE_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "approve_review_item": ApproveReviewItemResponse,
    "get_review_item": GetReviewItemResponse,
    "list_review_items": ListReviewItemsResponse,
    "reject_review_item": ApproveReviewItemResponse,
}
