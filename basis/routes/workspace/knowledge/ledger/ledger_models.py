"""Pydantic models for workspace ledger routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RememberProposalRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    chunk_id: str | None = Field(
        default=None,
        description="Optional ledger chunk to cite as evidence for this proposal.",
    )
    quote: str | None = Field(
        default=None,
        description="Optional quote override when chunk_id is set.",
    )
