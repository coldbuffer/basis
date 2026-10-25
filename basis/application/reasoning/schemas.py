"""Pydantic models for named tool arguments and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from basis.application.schema_base import ExtraAllowedModel

class GetRuleInput(ExtraAllowedModel):
    rule_id: str = Field(min_length=1)

class GetRuleResponse(ExtraAllowedModel):
    rule: dict[str, Any]

class ListRulesInput(ExtraAllowedModel):
    limit: int = Field(default=100, ge=1, le=200)

class ListRulesResponse(ExtraAllowedModel):
    rules: list[Any] = Field(default_factory=list)

class RunReasoningInput(ExtraAllowedModel):
    facts: list[str] | None = None
    rules: list[str] = Field(min_length=1)
    facts_limit: int = Field(default=200, ge=1, le=500)
    apply_to_graph: bool = False
    mode: str = "forward"
    inferred_edge_type: str | None = None
    chunk_id: str | None = None
    quote: str | None = None

class RunReasoningResponse(ExtraAllowedModel):
    inferred_facts: list[str] = Field(default_factory=list)
    rules_fired: int | None = None
    added_edges: int | None = None
    mutated: bool | None = None
    proof_chains: list[Any] = Field(default_factory=list)
    facts_source: str | None = None
    ground_facts: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] | None = None

TOOL_INPUT_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "get_rule": GetRuleInput,
    "list_rules": ListRulesInput,
    "run_reasoning": RunReasoningInput,
}

TOOL_RESPONSE_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "get_rule": GetRuleResponse,
    "list_rules": ListRulesResponse,
    "run_reasoning": RunReasoningResponse,
}
