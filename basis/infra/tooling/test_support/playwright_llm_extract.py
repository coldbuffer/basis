"""Playwright E2E: seed Chat credentials and stub semantica LLM extract (data/e2e only)."""

from __future__ import annotations

from typing import Any

from basis.domain.tenancy.admin.store import AdminStore
from basis.infra.tooling.test_support.llm_extract_stub import (
    PLAYWRIGHT_E2E_CHAT_LLM,
    graph_builder_stub_build,
)

_GRAPH_BUILDER_PATCHED = False


def ensure_playwright_e2e_chat_llm(store: AdminStore) -> None:
    """Persist legacy chat settings when the Playwright data dir has no configured model."""
    current = store.get_chat_llm_settings()
    if (current.get("api_key") or "").strip() and (current.get("model") or "").strip():
        return
    store._put_setting("chat_api_key", PLAYWRIGHT_E2E_CHAT_LLM["api_key"])
    store._put_setting("chat_model", PLAYWRIGHT_E2E_CHAT_LLM["model"])
    store._put_setting("chat_base_url", PLAYWRIGHT_E2E_CHAT_LLM["base_url"])


def install_playwright_e2e_graph_builder_stub() -> None:
    """Patch GraphBuilder.build once per process (idempotent)."""
    global _GRAPH_BUILDER_PATCHED
    if _GRAPH_BUILDER_PATCHED:
        return
    try:
        from semantica.kg import GraphBuilder
    except ImportError:
        return

    _orig = GraphBuilder.build

    def _wrapped(
        self: Any,
        sources: Any,
        second_arg: Any = None,
        pipeline_id: Any = None,
        **options: Any,
    ) -> dict[str, Any]:
        return graph_builder_stub_build(
            lambda s, sa=None, pid=None, **kw: _orig(self, s, sa, pipeline_id=pid, **kw),
            sources,
            second_arg,
            pipeline_id,
            **options,
        )

    GraphBuilder.build = _wrapped  # type: ignore[method-assign]
    _GRAPH_BUILDER_PATCHED = True
