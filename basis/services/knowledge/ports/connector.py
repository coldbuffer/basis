"""Knowledge-side facade for ``domain.connector`` (import-linter whitelist)."""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "LockedCanonicalConn": ("basis.services.connector.canonical_db", "LockedCanonicalConn"),
    "is_knowledge_store": ("basis.services.connector.canonical_db", "is_knowledge_store"),
    "ConnectorRuntime": ("basis.services.connector.runtime", "ConnectorRuntime"),
    "UnifiedReadResult": ("basis.services.connector.runtime", "UnifiedReadResult"),
    "SqlAlchemyStreamAdapter": (
        "basis.services.connector.adapters.sql",
        "SqlAlchemyStreamAdapter",
    ),
}


def __getattr__(name: str) -> Any:
    spec = _LAZY_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = spec
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def connector_runtime_for_store(store: object) -> Any:
    if not hasattr(store, "connector_runtime"):
        raise TypeError("store does not expose connector_runtime")
    return store.connector_runtime()
