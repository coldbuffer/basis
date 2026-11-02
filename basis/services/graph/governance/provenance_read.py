"""Provenance lineage reads and export."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import networkx as nx

from semantica.provenance.integrity import verify_checksum

logger = logging.getLogger(__name__)

_UNSAFE_FILENAME_CHARS = re.compile(r'[\r\n\x00"\\]')
_MAX_FILENAME_ID_LEN = 128

_AGENT_TYPES = {"person", "organization", "system", "agent"}
_ACTIVITY_TYPES = {"action", "event", "process", "activity", "decision", "publication"}


def _safe_content_disposition_filename(node_id: str, suffix: str) -> str:
    sanitized = _UNSAFE_FILENAME_CHARS.sub("_", str(node_id))[:_MAX_FILENAME_ID_LEN]
    return f"{sanitized}{suffix}"


def _classify_prov(node_type: str) -> tuple[str, str]:
    lowered = node_type.lower()
    if lowered in _AGENT_TYPES:
        return "Agent", "group_agent"
    if lowered in _ACTIVITY_TYPES:
        return "Activity", "group_activity"
    return "Entity", "group_entity"


def _add_chain_nodes(chain: list[Any], nodes: list[dict[str, Any]], seen_nodes: set[str]) -> None:
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get("entity_id") or "")
        if not eid or eid in seen_nodes:
            continue
        seen_nodes.add(eid)
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        label = str(metadata.get("title") or metadata.get("label") or eid)
        prov_type, parent_id = _classify_prov(str(entry.get("entity_type", "entity")))
        nodes.append(
            {
                "id": eid,
                "label": label,
                "prov_type": prov_type,
                "parent_id": parent_id,
                "source_document": entry.get("source_document") or None,
                "source_location": entry.get("source_location") or None,
                "source_quote": entry.get("source_quote") or None,
                "confidence": entry.get("confidence"),
                "checksum": entry.get("checksum") or None,
            }
        )


def _add_chain_edges(
    chain: list[Any],
    edges: list[dict[str, Any]],
    seen_edges: set[tuple[str, str, str]],
    direction: str,
) -> None:
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get("entity_id") or "")
        if not eid:
            continue
        parents: list[str] = []
        if entry.get("parent_entity_id"):
            parents.append(str(entry.get("parent_entity_id")))
        used = entry.get("used_entities")
        if isinstance(used, list):
            for u in used:
                if u and str(u) not in parents:
                    parents.append(str(u))

        activity = str(entry.get("activity_id") or "wasDerivedFrom")
        for src in parents:
            edge_key = (src, eid, direction)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(
                {
                    "id": f"{src}-{eid}-{direction}",
                    "source": src,
                    "target": eid,
                    "label": activity,
                    "direction": direction,
                }
            )


def _transform_audit_lineage(
    lineage: dict[str, Any],
    node_id: str,
    descendants: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    ancestor_chain = lineage.get("lineage_chain") or lineage.get("entries") or []
    descendant_chain = (
        (descendants or {}).get("descendant_chain")
        or (descendants or {}).get("entries")
        or []
    )

    _add_chain_nodes(ancestor_chain, nodes, seen_nodes)
    _add_chain_nodes(descendant_chain, nodes, seen_nodes)
    _add_chain_edges(ancestor_chain, edges, seen_edges, "upstream")
    _add_chain_edges(descendant_chain, edges, seen_edges, "downstream")

    for edge in edges:
        for endpoint in (edge["source"], edge["target"]):
            if endpoint not in seen_nodes:
                seen_nodes.add(endpoint)
                prov_type, parent_id = _classify_prov("entity")
                nodes.append(
                    {
                        "id": endpoint,
                        "label": endpoint,
                        "prov_type": prov_type,
                        "parent_id": parent_id,
                        "source_document": None,
                        "source_location": None,
                        "source_quote": None,
                        "confidence": None,
                        "checksum": None,
                    }
                )

    return {"nodes": nodes, "edges": edges, "source": "audit"}


def build_provenance(session: Any, node_id: str | None = None) -> dict[str, Any]:
    if not node_id:
        return {"nodes": [], "edges": [], "source": "graph_traversal"}

    try:
        manager = getattr(session, "provenance_manager", None)
        if manager is not None:
            lineage = manager.get_lineage(node_id)
            if lineage and lineage.get("entity_count", 0) > 0:
                integrity_ok = lineage.get("integrity_verified")
                if integrity_ok is None:
                    entries = lineage.get("lineage_chain") or lineage.get("entries") or []
                    integrity_ok = all(verify_checksum(entry) for entry in entries)
                if integrity_ok:
                    descendants: dict[str, Any] = {}
                    try:
                        descendants = manager.get_descendants(node_id) or {}
                    except Exception as exc:
                        logger.warning(
                            "ProvenanceManager get_descendants failed for %s: %s",
                            node_id,
                            exc,
                        )
                    return _transform_audit_lineage(lineage, node_id, descendants)
                logger.warning(
                    "Provenance integrity verification failed for %s, falling back to graph traversal",
                    node_id,
                )
    except Exception as exc:
        logger.warning(
            "ProvenanceManager get_lineage failed for %s, falling back to graph traversal: %s",
            node_id,
            exc,
        )

    if node_id not in session.graph.nodes:
        return {"nodes": [], "edges": [], "source": "graph_traversal"}

    graph = nx.DiGraph()
    graph.add_node(node_id)

    hop_nodes = {node_id}
    for edge in session.graph.edges:
        if edge.source_id == node_id or edge.target_id == node_id:
            graph.add_edge(edge.source_id, edge.target_id, label=edge.edge_type)
            hop_nodes.add(edge.source_id)
            hop_nodes.add(edge.target_id)

    for edge in session.graph.edges:
        if edge.source_id in hop_nodes or edge.target_id in hop_nodes:
            graph.add_edge(edge.source_id, edge.target_id, label=edge.edge_type)

    subgraph = nx.ego_graph(graph, node_id, radius=2, undirected=True)
    provenance_nodes: list[dict[str, Any]] = []
    for graph_node_id in subgraph.nodes():
        node = session.graph.nodes.get(graph_node_id)
        if node is None:
            continue
        prov_type, parent_id = _classify_prov(node.node_type)
        provenance_nodes.append(
            {
                "id": graph_node_id,
                "label": node.content or graph_node_id,
                "prov_type": prov_type,
                "parent_id": parent_id,
            }
        )

    provenance_edges: list[dict[str, Any]] = []
    for source, target, data in subgraph.edges(data=True):
        if target == node_id:
            direction = "upstream"
        elif source == node_id:
            direction = "downstream"
        else:
            direction = "lateral"
        provenance_edges.append(
            {
                "id": f"{source}-{target}",
                "source": source,
                "target": target,
                "label": data.get("label", "related_to"),
                "direction": direction,
            }
        )

    return {
        "nodes": provenance_nodes,
        "edges": provenance_edges,
        "source": "graph_traversal",
    }


def get_provenance_lineage(session: Any, node_id: str | None = None) -> dict[str, Any]:
    return build_provenance(session, node_id)


def _build_report(session: Any, node_id: str) -> dict[str, Any]:
    node = session.get_node(node_id)
    provenance = build_provenance(session, node_id)
    return {
        "node_id": node_id,
        "label": node.get("content", node_id) if node else node_id,
        "type": node.get("type", "entity") if node else "entity",
        "properties": node.get("metadata", node.get("properties", {})) if node else {},
        "lineage": provenance,
        "source": provenance.get("source", "graph_traversal"),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Provenance Report: {report['label']}",
        "",
        f"- Node ID: `{report['node_id']}`",
        f"- Type: `{report['type']}`",
        "",
        "## Properties",
    ]
    properties = report.get("properties", {})
    if properties:
        for key, value in properties.items():
            lines.append(f"- **{key}**: {value}")
    else:
        lines.append("- No properties recorded")

    lines.extend(["", "## Lineage Nodes"])
    for node in report.get("lineage", {}).get("nodes", []):
        line = f"- `{node['id']}` ({node['prov_type']}): {node['label']}"
        if node.get("source_document"):
            line += f" [source: {node['source_document']}]"
        if node.get("confidence") is not None:
            line += f" (confidence: {node['confidence']})"
        if node.get("checksum"):
            line += f" (checksum: {node['checksum'][:8]}...)"
        lines.append(line)

    edges = report.get("lineage", {}).get("edges", [])
    grouped_edges: dict[str, list[dict[str, Any]]] = {
        "upstream": [],
        "downstream": [],
        "lateral": [],
    }
    for edge in edges:
        direction = edge.get("direction", "lateral")
        if direction not in grouped_edges:
            direction = "lateral"
        grouped_edges[direction].append(edge)

    if grouped_edges["upstream"]:
        lines.extend(["", "## Upstream"])
        for edge in grouped_edges["upstream"]:
            lines.append(f"- `{edge['source']}` -[{edge['label']}]-> `{edge['target']}`")

    if grouped_edges["downstream"]:
        lines.extend(["", "## Downstream"])
        for edge in grouped_edges["downstream"]:
            lines.append(f"- `{edge['source']}` -[{edge['label']}]-> `{edge['target']}`")

    if grouped_edges["lateral"]:
        lines.extend(["", "## Lateral"])
        for edge in grouped_edges["lateral"]:
            lines.append(f"- `{edge['source']}` -[{edge['label']}]-> `{edge['target']}`")

    return "\n".join(lines)


def export_provenance_report(
    session: Any,
    node_id: str,
    *,
    format: str = "json",
) -> tuple[bytes | str, str, str]:
    """Return (body, media_type, content_disposition attachment filename)."""
    report = _build_report(session, node_id)
    safe_name = _safe_content_disposition_filename(node_id, "_provenance")
    if format.lower() in {"md", "markdown"}:
        content = _render_markdown(report)
        return (
            content,
            "text/plain; charset=utf-8",
            f'attachment; filename="{safe_name}.md"',
        )
    content = json.dumps(report, indent=2, default=str)
    return (
        content,
        "application/json",
        f'attachment; filename="{safe_name}.json"',
    )
