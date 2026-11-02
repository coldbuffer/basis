"""Per-workspace graph session cache (read/index/analytics)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from basis.services.graph.projection.session import GraphSession
from basis.services.graph.session.probe import build_graph_adapter
from basis.services.knowledge.store import KnowledgeStore


def _rebuild_graph_adapter(basis_session: GraphSession) -> Any:
    return build_graph_adapter(basis_session)


def _adapter_wrapped_graph(adapter: Any | None) -> Any | None:
    if adapter is None:
        return None
    return getattr(adapter, "graph", None)


@dataclass
class GraphRuntime:
    workspace_id: str
    projection_revision: int
    basis: GraphSession
    adapter: Any | None
    last_access: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_access = time.monotonic()


class GraphSessionRegistry:
    """One graph adapter per workspace projection revision; single-flight load per workspace."""

    def __init__(self, *, idle_seconds: int = 1800) -> None:
        self._idle_seconds = idle_seconds
        self._cache: dict[str, GraphRuntime] = {}
        self._guard = threading.Lock()
        self._load_locks: dict[str, threading.Lock] = {}

    def get(
        self,
        workspace_id: str,
        *,
        knowledge: KnowledgeStore,
        basis_for_workspace: Callable[[str], GraphSession],
    ) -> GraphRuntime:
        revision = knowledge.get_projection_state(workspace_id)["revision"]

        with self._guard:
            cached = self._cache.get(workspace_id)
            if cached is not None and cached.projection_revision == revision:
                if _adapter_wrapped_graph(cached.adapter) is not cached.basis.graph:
                    cached.adapter = _rebuild_graph_adapter(cached.basis)
                cached.touch()
                return cached

        load_lock = self._load_locks.setdefault(workspace_id, threading.Lock())
        with load_lock:
            with self._guard:
                cached = self._cache.get(workspace_id)
                if cached is not None and cached.projection_revision == revision:
                    if _adapter_wrapped_graph(cached.adapter) is not cached.basis.graph:
                        cached.adapter = _rebuild_graph_adapter(cached.basis)
                    cached.touch()
                    return cached

            basis_session = basis_for_workspace(workspace_id)
            adapter_session = _rebuild_graph_adapter(basis_session)

            runtime = GraphRuntime(
                workspace_id=workspace_id,
                projection_revision=revision,
                basis=basis_session,
                adapter=adapter_session,
            )
            with self._guard:
                self._cache[workspace_id] = runtime
            return runtime

    def invalidate(self, workspace_id: str) -> None:
        with self._guard:
            self._cache.pop(workspace_id, None)

    def evict_idle(self) -> int:
        cutoff = time.monotonic() - self._idle_seconds
        removed = 0
        with self._guard:
            stale = [workspace_id for workspace_id, rt in self._cache.items() if rt.last_access < cutoff]
            for workspace_id in stale:
                self._cache.pop(workspace_id, None)
                removed += 1
        return removed
