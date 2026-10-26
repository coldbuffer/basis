"""Per-workspace agent governor policy (F-GOV-04)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from basis.domain.errors import AdminError
from basis.domain.ontology.mappings.entity_type import (
    entity_type_surface_phrases_from_config,
    filter_type_phrases,
)

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

    def entity_type_surface_phrases(self) -> list[str]:
        return filter_type_phrases(entity_type_surface_phrases_from_config(self))

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("entity_type_surface_phrases_json", None)
        data["entity_type_surface_phrases"] = self.entity_type_surface_phrases()
        return data


def validate_governance_config(config: GovernanceConfig) -> None:
    if config.governor_interval_minutes < 0:
        raise AdminError(422, "bad_interval", "治理扫描间隔无效")
    if not 0.0 <= config.governor_confidence_min <= 1.0:
        raise AdminError(422, "bad_confidence_min", "confidence_min 须在 0–1 之间")
