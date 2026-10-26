"""Pydantic models for ontology MCP tool arguments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from basis.application.schema_base import ExtraAllowedModel


class ListOntologyRegistryInput(ExtraAllowedModel):
    q: str | None = None
    status: str | None = None
    format: str | None = None


class GetOntologyGraphInput(ExtraAllowedModel):
    uri: str = Field(min_length=1)


class SearchOntologyEntitiesInput(ExtraAllowedModel):
    q: str = Field(min_length=1)
    entity_type: Literal["class", "property", "individual", "concept", "scheme"] | None = None
    limit: int = Field(default=50, ge=1, le=200)


class SuggestAlignmentTargetUriInput(ExtraAllowedModel):
    label: str = Field(min_length=1)
    entity_type: Literal["class", "property"] = "class"
    limit: int = Field(default=8, ge=1, le=32)


class ListVocabularyAlignmentsInput(ExtraAllowedModel):
    uri: str | None = Field(
        default=None,
        description="Filter alignments whose source or target URI starts with this prefix.",
    )
    limit: int = Field(default=100, ge=1, le=500)


class UpsertVocabularyAlignmentInput(ExtraAllowedModel):
    source_uri: str = Field(min_length=1)
    target_uri: str = Field(min_length=1)
    relation: Literal[
        "owl:equivalentClass",
        "owl:equivalentProperty",
        "skos:exactMatch",
        "skos:closeMatch",
        "skos:broadMatch",
        "skos:narrowMatch",
        "skos:relatedMatch",
    ]
    source_label: str | None = None
    target_label: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: str | None = None
    source: str | None = None
    reviewer: str | None = None


class DeleteVocabularyAlignmentInput(ExtraAllowedModel):
    alignment_id: str = Field(min_length=1)


class SuggestVocabularyAlignmentsInput(ExtraAllowedModel):
    source_ontology_uri: str | None = None
    target_ontology_uri: str | None = None
    threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    limit: int = Field(default=25, ge=1, le=100)


class SaveOntologyDraftInput(ExtraAllowedModel):
    ontology_uri: str = Field(min_length=1)
    diff: dict[str, Any]
    summary: str | None = None


class ListOntologyDraftsInput(ExtraAllowedModel):
    ontology_uri: str = Field(min_length=1)


class GetOntologyDraftInput(ExtraAllowedModel):
    draft_id: str = Field(min_length=1)


class SubmitOntologyProposalInput(ExtraAllowedModel):
    draft_id: str = Field(min_length=1)
    ontology_uri: str = Field(min_length=1)
    summary: str | None = None
    reviewer: str | None = None


class ListOntologyProposalsInput(ExtraAllowedModel):
    ontology_uri: str | None = None
    state: Literal["draft", "proposed", "approved", "published", "rejected"] | None = None


class OntologyProposalIdInput(ExtraAllowedModel):
    proposal_id: str = Field(min_length=1)


class CommentOntologyProposalInput(ExtraAllowedModel):
    proposal_id: str = Field(min_length=1)
    element_uri: str = Field(min_length=1, max_length=2048)
    text: str = Field(min_length=1, max_length=4000)


class ListOntologyVersionsInput(ExtraAllowedModel):
    ontology_uri: str = Field(min_length=1)


class CompareOntologyVersionsInput(ExtraAllowedModel):
    ontology_uri: str = Field(min_length=1)
    version1: str = Field(min_length=1)
    version2: str = Field(min_length=1)


class ToggleOntologyInput(ExtraAllowedModel):
    ontology_uri: str = Field(min_length=1)


class RestoreOntologyVersionInput(ExtraAllowedModel):
    ontology_uri: str = Field(min_length=1)
    target_version: str = Field(min_length=1)
    summary: str | None = None


TOOL_INPUT_MODELS: dict[str, type[ExtraAllowedModel]] = {
    "compare_ontology_versions": CompareOntologyVersionsInput,
    "approve_ontology_proposal": OntologyProposalIdInput,
    "comment_ontology_proposal": CommentOntologyProposalInput,
    "get_ontology_proposal": OntologyProposalIdInput,
    "publish_ontology_proposal": OntologyProposalIdInput,
    "reject_ontology_proposal": OntologyProposalIdInput,
    "get_ontology_draft": GetOntologyDraftInput,
    "get_ontology_graph": GetOntologyGraphInput,
    "list_ontology_drafts": ListOntologyDraftsInput,
    "list_ontology_proposals": ListOntologyProposalsInput,
    "list_ontology_registry": ListOntologyRegistryInput,
    "list_ontology_versions": ListOntologyVersionsInput,
    "save_ontology_draft": SaveOntologyDraftInput,
    "search_ontology_entities": SearchOntologyEntitiesInput,
    "suggest_alignment_target_uri": SuggestAlignmentTargetUriInput,
    "list_vocabulary_alignments": ListVocabularyAlignmentsInput,
    "upsert_vocabulary_alignment": UpsertVocabularyAlignmentInput,
    "delete_vocabulary_alignment": DeleteVocabularyAlignmentInput,
    "suggest_vocabulary_alignments": SuggestVocabularyAlignmentsInput,
    "submit_ontology_proposal": SubmitOntologyProposalInput,
    "toggle_ontology": ToggleOntologyInput,
    "restore_ontology_version_draft": RestoreOntologyVersionInput,
}
