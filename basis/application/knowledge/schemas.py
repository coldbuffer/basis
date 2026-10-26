"""Pydantic models for named tool arguments and responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from basis.application.schema_base import ExtraAllowedModel

class EntityFactsInput(ExtraAllowedModel):
    entity_id: str = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=100)

class EntityFactsResponse(ExtraAllowedModel):
    entity_id: str
    facts: list[Any] = Field(default_factory=list)
    derived_facts: list[Any] = Field(default_factory=list)

class GetChunkInput(ExtraAllowedModel):
    chunk_id: str = Field(min_length=1)

class GetChunkResponse(ExtraAllowedModel):
    chunk: dict[str, Any]

class GetStatementInput(ExtraAllowedModel):
    statement_id: str = Field(min_length=1)

class GetStatementResponse(ExtraAllowedModel):
    statement: dict[str, Any]

class ListDerivedFactsInput(ExtraAllowedModel):
    entity_id: str | None = None
    limit: int = Field(default=100, ge=1, le=200)

class ListDerivedFactsResponse(ExtraAllowedModel):
    entity_id: str | None = None
    derived_facts: list[Any] = Field(default_factory=list)

class ListMappingsInput(ExtraAllowedModel):
    status: str | None = None
    limit: int = Field(default=100, ge=1, le=200)

class ListMappingsResponse(ExtraAllowedModel):
    mappings: list[Any] = Field(default_factory=list)


class ListSurfacePhrasesInput(ExtraAllowedModel):
    limit: int = Field(default=100, ge=1, le=200)


class ListSurfacePhrasesResponse(ExtraAllowedModel):
    phrases: list[str] = Field(default_factory=list)


class ListEntityTypeObjectLabelsInput(ExtraAllowedModel):
    limit: int = Field(default=100, ge=1, le=200)


class ListEntityTypeObjectLabelsResponse(ExtraAllowedModel):
    labels: list[str] = Field(default_factory=list)
    type_surface_phrases: list[str] = Field(default_factory=list)


class ProposeMappingInput(ExtraAllowedModel):
    signature: str | None = Field(default=None, max_length=512)
    subject_id: str | None = Field(
        default=None,
        max_length=2048,
        description="Direct rdf:type assign when target_kind=class (with target_uri); omit signature.",
    )
    target_uri: str | None = Field(default=None, max_length=2048)
    target_kind: Literal["class", "property", "none"] = "property"
    direction: Literal["forward", "reverse", "n/a"] = "forward"
    status: Literal["proposed", "confirmed"] = "proposed"
    why: str | None = Field(default=None, max_length=2000)


class AssignEntityTypesInput(ExtraAllowedModel):
    assignments: list[dict[str, Any]] = Field(min_length=1, max_length=200)
    replace_existing: bool = True


class ClearEntityTypesInput(ExtraAllowedModel):
    subject_ids: list[str] = Field(min_length=1, max_length=200)


class InvalidateEntitiesInput(ExtraAllowedModel):
    entity_ids: list[str] = Field(min_length=1, max_length=200)


class DeleteDocumentInput(ExtraAllowedModel):
    document_id: str = Field(
        min_length=1,
        description="Internal document UUID or external doc_id (same as HTTP DELETE …/documents/{id}).",
    )


class DeleteEntityInput(ExtraAllowedModel):
    entity_id: str = Field(min_length=1, description="Ledger entity id (hard delete; not projection archive).")


class UpdateMappingStatusInput(ExtraAllowedModel):
    mapping_id: str = Field(min_length=1)
    status: Literal["confirmed", "rejected", "superseded"]
    why: str | None = Field(default=None, max_length=2000)

class ListTypedFactsInput(ExtraAllowedModel):
    limit: int = Field(default=100, ge=1, le=200)

class ListTypedFactsResponse(ExtraAllowedModel):
    facts: list[Any] = Field(default_factory=list)

class ProposeRememberInput(ExtraAllowedModel):
    content: str = Field(min_length=1)
    source: str | None = None
    chunk_id: str | None = Field(
        default=None,
        description="Optional evidence chunk from search_chunks/get_chunk; omit for agent anchor.",
    )
    quote: str | None = Field(
        default=None,
        description="Optional excerpt; defaults to chunk text or proposal content.",
    )

class SearchChunksInput(ExtraAllowedModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1)
    document_id: str | None = None
    entity_id: str | None = None
    as_of: str | None = None
    created_after: str | None = None
    created_before: str | None = None
    mode: Literal["keyword", "semantic", "hybrid"] | None = None
    limit_max: int | None = Field(default=None, ge=1)

class SearchChunksResponse(ExtraAllowedModel):
    query: str | None = None
    mode: str | None = None
    chunks: list[Any] = Field(default_factory=list)

TOOL_INPUT_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "entity_facts": EntityFactsInput,
    "get_chunk": GetChunkInput,
    "get_statement": GetStatementInput,
    "list_derived_facts": ListDerivedFactsInput,
    "list_entity_type_object_labels": ListEntityTypeObjectLabelsInput,
    "list_mappings": ListMappingsInput,
    "list_surface_phrases": ListSurfacePhrasesInput,
    "list_typed_facts": ListTypedFactsInput,
    "assign_entity_types": AssignEntityTypesInput,
    "clear_entity_types": ClearEntityTypesInput,
    "invalidate_entities": InvalidateEntitiesInput,
    "delete_document": DeleteDocumentInput,
    "delete_entity": DeleteEntityInput,
    "propose_mapping": ProposeMappingInput,
    "propose_remember": ProposeRememberInput,
    "search_chunks": SearchChunksInput,
    "update_mapping_status": UpdateMappingStatusInput,
}

TOOL_RESPONSE_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "entity_facts": EntityFactsResponse,
    "get_chunk": GetChunkResponse,
    "get_statement": GetStatementResponse,
    "list_derived_facts": ListDerivedFactsResponse,
    "list_mappings": ListMappingsResponse,
    "list_entity_type_object_labels": ListEntityTypeObjectLabelsResponse,
    "list_surface_phrases": ListSurfacePhrasesResponse,
    "list_typed_facts": ListTypedFactsResponse,
    "search_chunks": SearchChunksResponse,
}
