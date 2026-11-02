"""Workspace temporal graph bounds and snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from basis.services.graph.reads.diff import parse_query_dt


def get_temporal_bounds(session: Any) -> dict[str, Any]:
    """Same contract as Explorer ``temporal_bounds`` route (session.get_temporal_bounds)."""
    bounds = session.get_temporal_bounds()
    if not isinstance(bounds, dict):
        return {"min": None, "max": None}
    return dict(bounds)


def get_temporal_snapshot(session: Any, at: str | None = None) -> dict[str, Any]:
    at_time = (
        parse_query_dt(at)
        if at
        else datetime.now(timezone.utc).replace(tzinfo=None)
    )
    active_nodes = session.get_active_nodes(at_time=at_time)
    active_ids = [node.get("id") for node in active_nodes if node.get("id")]
    return {
        "timestamp": at_time.isoformat(),
        "active_node_ids": active_ids,
        "active_node_count": len(active_ids),
    }


def detect_temporal_patterns(session: Any) -> dict[str, Any]:
    try:
        from semantica.kg import TemporalPatternDetector
    except ImportError:
        return {"patterns": []}
    detector = TemporalPatternDetector()
    graph_dict = session.build_graph_dict()
    patterns = detector.detect_temporal_patterns(graph_dict)
    if isinstance(patterns, dict):
        patterns = patterns.get("patterns", [])
    if not isinstance(patterns, list):
        patterns = []
    return {"patterns": patterns}
