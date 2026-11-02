"""Optional runtime capability probes (graph session, etc.)."""

from __future__ import annotations


def graph_runtime_available() -> bool:
    """Workspace graph session HTTP stack (``BasisGraphSession``) is always available."""
    return True


def platform_capabilities() -> dict[str, bool]:
    return {
        "graph_snapshot": True,
        "graph_runtime": graph_runtime_available(),
    }


def _role_can_write(role: str) -> bool:
    from basis.services.knowledge.models import ROLE_RANK

    return ROLE_RANK.get(role, 0) >= ROLE_RANK["editor"]


def workspace_capabilities(role: str) -> dict[str, bool | str | None]:
    """Per-workspace graph console feature flags for authorized callers (design §12)."""
    can_write = _role_can_write(role)
    return {
        "graph": True,
        "graph_write": can_write,
        "temporal": True,
        "decisions": True,
        "sparql": True,
        "reasoning": True,
        "enrichment": True,
        "review": True,
        "direct_graph_merge": False,
        "direct_graph_import": False,
        "import_export": can_write,
        "provenance": True,
        "vocabulary": True,
        "mappings": True,
        "agent_memory": False,
        "graph_runtime": True,
        "diagnostic": None,
    }
