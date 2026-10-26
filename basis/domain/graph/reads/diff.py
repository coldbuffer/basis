"""Graph state diff between two instants (F-DIFF-01 MVP)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def parse_query_dt(value: str) -> datetime:
    if not value:
        raise ValueError("timestamp required")
    text = str(value).strip()
    if re.fullmatch(r"\d{4}", text):
        text = f"{text}-01-01"
    text = text.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _node_fingerprint(node: Dict[str, Any]) -> str:
    props = node.get("properties") or {}
    payload = {"type": node.get("type"), "properties": props}
    return json.dumps(payload, sort_keys=True, default=str)


def _edge_key(edge: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(edge.get("source_id") or ""),
            str(edge.get("target_id") or ""),
            str(edge.get("type") or edge.get("edge_type") or ""),
        ]
    )


def diff_graph_states(start: Dict[str, Any], end: Dict[str, Any]) -> Dict[str, Any]:
    start_nodes = {n["id"]: n for n in start.get("nodes", []) if n.get("id")}
    end_nodes = {n["id"]: n for n in end.get("nodes", []) if n.get("id")}
    start_ids = set(start_nodes)
    end_ids = set(end_nodes)

    added_nodes = sorted(end_ids - start_ids)
    removed_nodes = sorted(start_ids - end_ids)
    modified_nodes: List[Dict[str, str]] = []
    for node_id in sorted(start_ids & end_ids):
        if _node_fingerprint(start_nodes[node_id]) != _node_fingerprint(end_nodes[node_id]):
            modified_nodes.append({"id": node_id, "change": "properties"})

    start_edges = {_edge_key(e): e for e in start.get("edges", [])}
    end_edges = {_edge_key(e): e for e in end.get("edges", [])}
    start_edge_keys = set(start_edges)
    end_edge_keys = set(end_edges)

    added_edges = [end_edges[k] for k in sorted(end_edge_keys - start_edge_keys)]
    removed_edges = [start_edges[k] for k in sorted(start_edge_keys - end_edge_keys)]

    return {
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "modified_nodes": modified_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "summary": {
            "nodes_added": len(added_nodes),
            "nodes_removed": len(removed_nodes),
            "nodes_modified": len(modified_nodes),
            "edges_added": len(added_edges),
            "edges_removed": len(removed_edges),
        },
    }


def diff_session_at(session: Any, from_time: str, to_time: str) -> Dict[str, Any]:
    start_dt = parse_query_dt(from_time)
    end_dt = parse_query_dt(to_time)
    start_state = session.graph.state_at(start_dt)
    end_state = session.graph.state_at(end_dt)
    body = diff_graph_states(start_state, end_state)
    body["from_time"] = start_dt.isoformat()
    body["to_time"] = end_dt.isoformat()
    return body
