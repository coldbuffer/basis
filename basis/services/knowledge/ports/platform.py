"""Structural types for platform services injected into workspace domain code."""

from __future__ import annotations

from typing import Any, Protocol


class WorkspaceAuditActor(Protocol):
    id: str


class WorkspaceAuditStore(Protocol):
    def record_audit(
        self,
        actor_id: str | None,
        action: str,
        target_type: str,
        target_id: str | None,
        detail: dict[str, Any] | None = None,
    ) -> None: ...


class EmbedSettingsStore(Protocol):
    def get_embed_settings(self, model_id: str | None = None) -> dict[str, str | None]: ...
