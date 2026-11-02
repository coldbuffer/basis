"""Pydantic models for workspace graph and chunk search routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GraphSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=50)
    at: str | None = Field(
        default=None,
        description="Optional temporal instant (ISO). When set, results are limited to nodes active at that instant.",
    )
    include_archived: bool = Field(
        default=False,
        description="When true, include projection nodes with status=archived in search results.",
    )


class SearchConfigRequest(BaseModel):
    chunk_backend: Literal["sqlite_ledger", "postgres_ledger"] = "sqlite_ledger"
    vector_backend: Literal["sqlite_vec", "pgvector"] = "sqlite_vec"
    embedding_model_id: str | None = None
    keyword_enabled: bool = True
    semantic_enabled: bool = True
    default_mode: Literal["keyword", "semantic", "hybrid"] = "hybrid"
    auto_index: bool = True


class ResolveNodeLabelsRequest(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=80)


class SearchReindexRequest(BaseModel):
    document_id: str | None = None
    version_id: str | None = None


class ReasoningRunRequest(BaseModel):
    rules: list[str] = Field(
        min_length=1,
        description="Non-empty list of forward-chaining rule strings (IF … THEN …).",
    )
    facts: list[str] | None = Field(
        default=None,
        description=(
            "Ground facts as predicate(Subject, Object) strings. "
            "Omit or pass an empty array to derive from materialized typed_facts (up to facts_limit)."
        ),
    )
    facts_limit: int = Field(
        default=200,
        ge=1,
        le=500,
        description="Max typed_facts rows when facts is omitted or empty.",
    )
    apply_to_graph: bool = Field(
        default=False,
        description="When true, persist inferred edges and derived facts (requires editor role).",
    )
    mode: str = Field(default="forward", description="Reasoning mode (forward chaining).")
    inferred_edge_type: str | None = Field(
        default=None,
        description="Optional edge type label when apply_to_graph is true.",
    )
    chunk_id: str | None = Field(
        default=None,
        description="Optional ledger chunk id to cite on inferred edges when apply_to_graph is true.",
    )
    quote: str | None = Field(
        default=None,
        description="Optional quote override for chunk_id evidence.",
    )


class ReasoningGroundFactsResponse(BaseModel):
    facts: list[str] = Field(default_factory=list)


class ReasoningProofChain(BaseModel):
    conclusion: str
    rule: str
    premises: list[str] = Field(default_factory=list)


class ReasoningDerivedPersistedSummary(BaseModel):
    created: int | None = None
    skipped: int | None = None


class ReasoningRunResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    inferred_facts: list[str] = Field(default_factory=list)
    rules_fired: int | None = None
    added_edges: int | None = None
    mutated: bool | None = None
    proof_chains: list[ReasoningProofChain] = Field(default_factory=list)
    facts_source: Literal["typed_facts", "request"] | None = None
    ground_facts: list[str] = Field(default_factory=list)
    derived_facts_persisted: ReasoningDerivedPersistedSummary | None = None
    projection: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
