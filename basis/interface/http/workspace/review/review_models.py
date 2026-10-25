"""Shared Pydantic models and helpers for workspace review routes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from basis.domain.knowledge.services.review_resolve_approve import ledger_entity_merge_ids


class CreateEntityMergeReviewRequest(BaseModel):
    primary_id: str = Field(min_length=1)
    duplicate_ids: list[str] = Field(min_length=1)


class ResolveReviewRequest(BaseModel):
    rationale: str | None = None
    primary_id: str | None = Field(
        default=None,
        description="For `entity_cluster` approve: ledger entity id to keep as primary (F-GOV-04).",
    )


class ApproveReviewItemResponse(BaseModel):
    """Approve review item (merge, import, remember, …) including optional governance decision id."""

    model_config = ConfigDict(extra="allow")

    item: dict[str, Any]
    decision_id: str | None = None


__all__ = [
    "ApproveReviewItemResponse",
    "CreateEntityMergeReviewRequest",
    "ResolveReviewRequest",
    "ledger_entity_merge_ids",
]
