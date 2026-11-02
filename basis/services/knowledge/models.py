"""Domain models, row DTOs, governance policy, and role constants for Knowledge."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from basis.services.errors import AdminError
from basis.services.knowledge.blob_store import BlobRef
from basis.services.ontology.mappings.entity_type import (
    entity_type_surface_phrases_from_config,
    filter_type_phrases,
)

# ── Workspace membership roles ───────────────────────────────────────────────

ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}
WORKSPACE_ROLES = frozenset(ROLE_RANK)

# ── Ledger & ingest row DTOs ─────────────────────────────────────────────────


@dataclass(frozen=True)
class JobRow:
    id: str
    workspace_id: str
    kind: str
    subject_type: str
    subject_id: str
    status: str
    attempt: int
    progress: float | None
    error_code: str | None
    error_detail: dict[str, Any] | None
    options: dict[str, Any]
    result: dict[str, Any] | None
    created_at: str
    started_at: str | None
    finished_at: str | None


@dataclass(frozen=True)
class DocumentVersionRow:
    id: str
    document_id: str
    workspace_id: str
    version_no: int
    sha256: str
    blob_key: str
    byte_size: int
    status: str


@dataclass(frozen=True)
class StoreDocumentOutcome:
    document_id: str
    version_id: str
    blob: BlobRef
    version_no: int
    new_document: bool
    new_version: bool


# ── Governance config (F-GOV-04) ─────────────────────────────────────────────

DEFAULT_GOVERNOR_CONFIDENCE_MIN = 0.75
DEFAULT_GOVERNOR_INTERVAL_MINUTES = 1440


@dataclass(frozen=True)
class GovernanceConfig:
    workspace_id: str
    schema_version: int = 1
    governor_enabled: bool = False
    governor_interval_minutes: int = DEFAULT_GOVERNOR_INTERVAL_MINUTES
    governor_confidence_min: float = DEFAULT_GOVERNOR_CONFIDENCE_MIN
    governor_last_run_at: str | None = None
    governance_ontology_uri: str | None = None
    governance_shacl_turtle: str | None = None
    entity_type_surface_phrases_json: str | None = None
    vocabulary_alignment_requires_review: bool = False

    def entity_type_surface_phrases(self) -> list[str]:
        return filter_type_phrases(entity_type_surface_phrases_from_config(self))

    def interpretation_dict(self) -> dict[str, Any]:
        return {"entity_type_surface_phrases": self.entity_type_surface_phrases()}

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("entity_type_surface_phrases_json", None)
        return data


def validate_governance_config(config: GovernanceConfig) -> None:
    if config.governor_interval_minutes < 0:
        raise AdminError(422, "bad_interval", "治理扫描间隔无效")
    if not 0.0 <= config.governor_confidence_min <= 1.0:
        raise AdminError(422, "bad_confidence_min", "confidence_min 须在 0–1 之间")


# ── Structured entity sync models (data-model.md §18.4–18.5) ─────────────────


class ConnectorSourceConfig(BaseModel):
    """Normative config_json for ingest_sources with kind = 'connector'."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    poll_interval_minutes: int | None = Field(default=60, ge=1)

    @model_validator(mode="before")
    @classmethod
    def _strip_legacy_connection_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            data.pop("connection_name", None)
        return data

    last_sync_at: str | None = None


class ColumnMappingSpec(BaseModel):
    """Single element of source_table_mappings.column_mappings_json."""

    model_config = ConfigDict(extra="forbid")

    column: str = Field(min_length=1)
    kind: Literal["literal", "relation"] = "literal"
    surface_phrase: str = Field(min_length=1)
    predicate_uri: str | None = None
    datatype: str = "xsd:string"
    fk_target_table: str | None = None
    writable: bool = False


class StructuredImportProvenance(BaseModel):
    """Normative typed_facts.import_provenance_json for structured connector rows."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["structured_source"] = "structured_source"
    provider: str = Field(min_length=1)
    stream: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    mapping_id: str = Field(min_length=1)
    external_ref_id: str = Field(min_length=1)
    external_table: str = Field(min_length=1)
    external_pk: str = Field(min_length=1)
    column: str = Field(min_length=1)


class OutboxFieldChange(BaseModel):
    """Before/after diff for one mapped attribute in entity_sync_outbox."""

    model_config = ConfigDict(extra="forbid")

    old: Any = None
    new: Any = None
    predicate_uri: str | None = None
    statement_id: str | None = None


class OutboxPatchSpec(BaseModel):
    """Normative entity_sync_outbox.patch_json payload."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    stream_name: str = Field(min_length=1)
    mutation_operation: Literal["create", "update", "upsert", "delete"] = "update"
    external_table: str = Field(min_length=1)
    primary_key_column: str = Field(min_length=1)
    external_pk: str = Field(min_length=1)
    stream_params: dict[str, Any] = Field(default_factory=dict)
    changes: dict[str, OutboxFieldChange] = Field(default_factory=dict)


def _normalize_hash_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _normalize_hash_value(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_normalize_hash_value(v) for v in value]
    return str(value)


def compute_canonical_row_hash(
    row: dict[str, Any],
    *,
    label_column: str,
    column_mappings: list[ColumnMappingSpec],
) -> str:
    """Compute deterministic SHA-256 hex digest over mapped columns (data-model.md §18.5)."""
    payload: dict[str, Any] = {
        label_column: _normalize_hash_value(row.get(label_column)),
    }
    for mapping in column_mappings:
        payload[mapping.column] = _normalize_hash_value(row.get(mapping.column))
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
