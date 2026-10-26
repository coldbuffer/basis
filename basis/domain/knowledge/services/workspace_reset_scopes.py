"""Workspace reset scope normalization."""

from __future__ import annotations

from typing import Any

SCOPE_KNOWLEDGE = "knowledge"
SCOPE_GRAPH = "graph"
SCOPE_CONNECTORS = "connectors"
SCOPE_REASONING = "reasoning"
SCOPE_GOVERNANCE = "governance"

ALL_RESET_SCOPES = frozenset(
    {
        SCOPE_KNOWLEDGE,
        SCOPE_GRAPH,
        SCOPE_CONNECTORS,
        SCOPE_REASONING,
        SCOPE_GOVERNANCE,
    }
)

DEFAULT_RESET_SCOPES = frozenset(
    {
        SCOPE_KNOWLEDGE,
        SCOPE_GRAPH,
        SCOPE_CONNECTORS,
        SCOPE_REASONING,
    }
)


def normalize_reset_scopes(raw: Any) -> frozenset[str] | None:
    if raw is None:
        return DEFAULT_RESET_SCOPES
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple, set, frozenset)):
        items = list(raw)
    else:
        return None
    out: set[str] = set()
    for item in items:
        key = str(item or "").strip().lower()
        if not key:
            continue
        if key not in ALL_RESET_SCOPES:
            return None
        out.add(key)
    if not out:
        return None
    if SCOPE_KNOWLEDGE in out and SCOPE_GRAPH not in out:
        out.add(SCOPE_GRAPH)
    return frozenset(out)


def scopes_for_api(scopes: frozenset[str]) -> list[str]:
    return sorted(scopes)
