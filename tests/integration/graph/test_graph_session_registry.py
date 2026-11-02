"""Explorer session registry cache behavior."""

import time

from basis.services.graph.session.basis_graph_session import BasisGraphSession
from basis.services.graph.session.probe import build_graph_adapter
from basis.services.graph.session.registry import (
    GraphSessionRegistry,
    GraphRuntime,
    _adapter_wrapped_graph,
    _rebuild_graph_adapter,
)
from basis.services.graph.projection.session import GraphSession


def test_rebuild_graph_adapter_tracks_basis_graph_swap() -> None:
    session = GraphSession()
    session.add_node("a", "entity", content="A")
    stale = type("E", (), {"graph": session.graph})()
    assert _adapter_wrapped_graph(stale) is session.graph

    session.graph = GraphSession().graph
    session.add_node("b", "entity", content="B")
    assert _adapter_wrapped_graph(stale) is not session.graph

    fresh = _rebuild_graph_adapter(session)
    assert fresh is not None
    assert _adapter_wrapped_graph(fresh) is session.graph
    assert isinstance(fresh, BasisGraphSession)


def test_build_graph_adapter_is_basis() -> None:
    session = GraphSession()
    adapter = build_graph_adapter(session)
    assert isinstance(adapter, BasisGraphSession)


def test_evict_idle_drops_stale_runtimes() -> None:
    registry = GraphSessionRegistry(idle_seconds=1)
    session = GraphSession()
    registry._cache["kb-stale"] = GraphRuntime(
        workspace_id="kb-stale",
        projection_revision=1,
        basis=session,
        adapter=None,
        last_access=time.monotonic() - 10,
    )
    removed = registry.evict_idle()
    assert removed == 1
    assert "kb-stale" not in registry._cache
