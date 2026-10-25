"""Workspace governance / governor scheduler — KnowledgeStore API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from basis.domain.knowledge.governance_config import GovernanceConfig, validate_governance_config
from basis.domain.knowledge.persistence import sql_governance_config as gov_persist

if TYPE_CHECKING:
    from basis.domain.knowledge.store import KnowledgeStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GovernanceAccess:
    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def get_governance_config(self, workspace_id: str) -> GovernanceConfig:
        with self._store._lock:
            self._store._assert_workspace_exists(workspace_id)
            row = gov_persist.fetch_governance_config_row(self._store._conn, workspace_id)
            if row is None:
                now = _now()
                gov_persist.insert_default_governance_config(
                    self._store._conn, workspace_id, created_at=now, updated_at=now
                )
                self._store._conn.commit()
                return GovernanceConfig(workspace_id=workspace_id)
        return gov_persist.governance_config_from_row(row)

    def update_governance_config(
        self,
        workspace_id: str,
        *,
        governor_enabled: bool,
        governor_interval_minutes: int,
        governor_confidence_min: float,
        governance_ontology_uri: str | None = None,
        clear_governance_ontology_uri: bool = False,
    ) -> GovernanceConfig:
        existing = self.get_governance_config(workspace_id)
        ontology_uri = existing.governance_ontology_uri
        if clear_governance_ontology_uri:
            ontology_uri = None
        elif governance_ontology_uri is not None:
            ontology_uri = governance_ontology_uri.strip() or None
        shacl_turtle = existing.governance_shacl_turtle
        if ontology_uri != existing.governance_ontology_uri:
            shacl_turtle = None
        config = GovernanceConfig(
            workspace_id=workspace_id,
            schema_version=existing.schema_version,
            governor_enabled=governor_enabled,
            governor_interval_minutes=governor_interval_minutes,
            governor_confidence_min=governor_confidence_min,
            governor_last_run_at=existing.governor_last_run_at,
            governance_ontology_uri=ontology_uri,
            governance_shacl_turtle=shacl_turtle,
            entity_type_surface_phrases_json=existing.entity_type_surface_phrases_json,
        )
        validate_governance_config(config)
        with self._store._lock:
            now = _now()
            gov_persist.upsert_governance_config(
                self._store._conn, config, created_at=now, updated_at=now
            )
            self._store._conn.commit()
        return config

    def save_governance_shacl(
        self,
        workspace_id: str,
        *,
        ontology_uri: str,
        shacl_turtle: str,
    ) -> GovernanceConfig:
        uri = str(ontology_uri or "").strip()
        if not uri:
            raise ValueError("ontology_uri is required")
        existing = self.get_governance_config(workspace_id)
        turtle = str(shacl_turtle or "").strip() or None
        config = GovernanceConfig(
            workspace_id=workspace_id,
            schema_version=existing.schema_version,
            governor_enabled=existing.governor_enabled,
            governor_interval_minutes=existing.governor_interval_minutes,
            governor_confidence_min=existing.governor_confidence_min,
            governor_last_run_at=existing.governor_last_run_at,
            governance_ontology_uri=uri,
            governance_shacl_turtle=turtle,
            entity_type_surface_phrases_json=existing.entity_type_surface_phrases_json,
        )
        validate_governance_config(config)
        with self._store._lock:
            now = _now()
            gov_persist.upsert_governance_config(
                self._store._conn, config, created_at=now, updated_at=now
            )
            self._store._conn.commit()
        return config

    def touch_governor_last_run(self, workspace_id: str, run_at: str) -> None:
        _ = self.get_governance_config(workspace_id)
        with self._store._lock:
            gov_persist.touch_governor_last_run(
                self._store._conn, workspace_id, run_at, _now()
            )
            self._store._conn.commit()

    def list_governor_enabled_workspace_ids(self) -> list[str]:
        with self._store._lock:
            try:
                return gov_persist.list_governor_enabled_workspace_ids(self._store._conn)
            except Exception as exc:
                msg = str(exc).lower()
                if "governance_configs" in msg and (
                    "does not exist" in msg or "no such table" in msg
                ):
                    return []
                raise
