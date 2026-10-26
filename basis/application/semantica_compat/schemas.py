"""Pydantic models for Semantica-aligned MCP tool arguments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from basis.application.schema_base import ExtraAllowedModel


class ExtractEntitiesInput(ExtraAllowedModel):
    text: str | None = None
    chunk_id: str | None = None
    quote: str | None = None
    model: str | None = None
    language: str | None = None
    method: str | None = None
    confidence_threshold: float | None = None


class ExtractRelationsInput(ExtraAllowedModel):
    text: str | None = None
    chunk_id: str | None = None
    quote: str | None = None
    model: str | None = None
    language: str | None = None
    method: str | None = None


class RecordDecisionInput(ExtraAllowedModel):
    category: str
    scenario: str
    reasoning: str
    outcome: str
    confidence: float
    entities: list[Any] | None = None
    decision_maker: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    chunk_id: str | None = None
    quote: str | None = None


class QueryDecisionsInput(ExtraAllowedModel):
    query: str | None = None
    category: str | None = None
    limit: int = Field(default=10, ge=1, le=500)


class FindPrecedentsInput(ExtraAllowedModel):
    scenario: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=100)
    min_similarity: float = Field(default=0.05, ge=0.0, le=1.0)


class GetCausalChainInput(ExtraAllowedModel):
    decision_id: str = Field(min_length=1)
    direction: Literal["upstream", "downstream"] = "downstream"
    max_depth: int = Field(default=5, ge=1, le=20)


class AddEntityInput(ExtraAllowedModel):
    id: str = Field(min_length=1)
    label: str | None = None
    type: str = "Entity"
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunk_id: str | None = None
    quote: str | None = None


class AddRelationshipInput(ExtraAllowedModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: str = "RELATED_TO"
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunk_id: str | None = None
    quote: str | None = None


class GetGraphAnalyticsInput(ExtraAllowedModel):
    pass


class ExportGraphInput(ExtraAllowedModel):
    format: str = "json-ld"


class GetGraphSummaryInput(ExtraAllowedModel):
    pass


class QueryGraphInput(ExtraAllowedModel):
    mode: Literal["node", "neighbors", "search", "entities"] = "neighbors"
    node_id: str | None = None
    depth: int = Field(default=1, ge=1, le=5)
    relationship_types: list[str] | str | None = None
    query: str | None = None
    node_type: str | None = None
    limit: int | None = Field(default=None, ge=0, le=500)
    include_archived: bool = False


class UpdateNodeInput(ExtraAllowedModel):
    node_id: str = Field(min_length=1)
    properties: dict[str, Any]
    chunk_id: str | None = None
    quote: str | None = None
    rationale: str | None = None


class DeleteNodeInput(ExtraAllowedModel):
    node_id: str = Field(min_length=1)
    chunk_id: str | None = None
    quote: str | None = None
    rationale: str | None = None


TOOL_INPUT_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "extract_entities": ExtractEntitiesInput,
    "extract_relations": ExtractRelationsInput,
    "record_decision": RecordDecisionInput,
    "query_decisions": QueryDecisionsInput,
    "find_precedents": FindPrecedentsInput,
    "get_causal_chain": GetCausalChainInput,
    "add_entity": AddEntityInput,
    "add_relationship": AddRelationshipInput,
    "get_graph_analytics": GetGraphAnalyticsInput,
    "export_graph": ExportGraphInput,
    "get_graph_summary": GetGraphSummaryInput,
    "query_graph": QueryGraphInput,
    "update_node": UpdateNodeInput,
    "delete_node": DeleteNodeInput,
}

TOOL_RESPONSE_MODELS: dict[str, type[ExtraAllowedModel]] = {}
