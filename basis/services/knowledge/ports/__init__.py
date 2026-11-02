"""Workspace domain ports (interface/application adapters implement these at the edges)."""

from basis.services.knowledge.ports.platform import EmbedSettingsStore, WorkspaceAuditActor, WorkspaceAuditStore

__all__ = [
    "EmbedSettingsStore",
    "WorkspaceAuditActor",
    "WorkspaceAuditStore",
]
