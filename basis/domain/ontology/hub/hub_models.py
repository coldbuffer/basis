"""Pydantic models for ontology hub HTTP API (OpenAPI-compatible with Explorer)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PreviewOntologyRequest(BaseModel):
    url: str | None = None
    content: str | None = None
    format: str | None = None


class LoadOntologyRequest(BaseModel):
    url: str | None = None
    content: str | None = None
    format: str | None = None
    name: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreateOntologyRequest(BaseModel):
    mode: Literal["scratch", "data", "text"] = "scratch"
    namespace: str
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    sample_data: str | None = None
    schema_text: str | None = None
    provider: str | None = None
    model: str | None = None


class SKOSConceptSearchRequest(BaseModel):
    query: str
    scheme_uri: str | None = None


class ShaclGenerateRequest(BaseModel):
    uri: str
    quality_tier: Literal["standard", "strict"] = "strict"


class ShaclValidateRequest(BaseModel):
    uri: str | None = None
    shacl_turtle: str


class DraftRequest(BaseModel):
    ontology_uri: str
    diff: "DraftDiff"
    author: str
    summary: str | None = None
    timestamp: str | None = None


class ProposalRequest(BaseModel):
    draft_id: str
    ontology_uri: str
    summary: str
    reviewer: str | None = None


class CommentRequest(BaseModel):
    element_uri: str
    text: str
    author: str


class VersionCompareRequest(BaseModel):
    version1: str
    version2: str


class OntologyEdgeChange(BaseModel):
    source: str
    target: str
    type: str
    id: str | None = None


class DraftDiff(BaseModel):
    added_classes: list[str] = Field(default_factory=list)
    removed_classes: list[str] = Field(default_factory=list)
    modified_classes: dict[str, dict[str, Any]] = Field(default_factory=dict)
    added_properties: list[str] = Field(default_factory=list)
    removed_properties: list[str] = Field(default_factory=list)
    modified_properties: dict[str, dict[str, Any]] = Field(default_factory=dict)
    added_individuals: list[str] = Field(default_factory=list)
    removed_individuals: list[str] = Field(default_factory=list)
    added_edges: list[OntologyEdgeChange] = Field(default_factory=list)
    removed_edges: list[str] = Field(default_factory=list)
    added_restrictions: list[dict[str, Any]] = Field(default_factory=list)
    removed_restrictions: list[dict[str, Any]] = Field(default_factory=list)
    added_axioms: list[dict[str, Any]] = Field(default_factory=list)
    removed_axioms: list[dict[str, Any]] = Field(default_factory=list)
    annotation_changes: dict[str, dict[str, Any]] = Field(default_factory=dict)


class DraftResponse(BaseModel):
    draft_id: str
    ontology_uri: str
    diff: DraftDiff
    author: str
    summary: str | None = None
    created_at: str
    updated_at: str


class ProposalResponse(BaseModel):
    proposal_id: str
    draft_id: str
    ontology_uri: str
    summary: str
    author: str
    reviewer: str | None = None
    state: Literal["draft", "proposed", "approved", "published", "rejected"]
    impact_analysis: dict[str, Any] = Field(default_factory=dict)
    shacl_validation: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    comments: list[dict[str, Any]] = Field(default_factory=list)


class VersionEntry(BaseModel):
    version_id: str
    ontology_uri: str
    state: Literal["draft", "published"]
    author: str
    date: str
    diff_summary: dict[str, Any] = Field(default_factory=dict)
