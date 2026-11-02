"""Graph enrichment writes (entity merge)."""

from __future__ import annotations

from typing import Any

from basis.services.errors import AdminError


def merge_nodes(
    session: Any,
    *,
    primary_id: str,
    duplicate_ids: list[str],
) -> dict[str, Any]:
    node = session.get_node(primary_id)
    if node is None:
        raise AdminError(404, "not_found", f"Primary node '{primary_id}' not found")

    removed: list[str] = []
    edges_updated = 0
    graph = session.graph

    for duplicate_id in duplicate_ids:
        if duplicate_id == primary_id or duplicate_id not in graph:
            continue

        duplicate_node = graph.nodes.get(duplicate_id)
        primary_node = graph.nodes.get(primary_id)
        if duplicate_node and primary_node:
            for key, value in (duplicate_node.properties or {}).items():
                if key not in (primary_node.properties or {}):
                    primary_node.properties[key] = value
                    primary_node.metadata[key] = value

        edges_to_add = []
        retained_edges = []
        for edge in list(graph.edges):
            if edge.source_id == duplicate_id or edge.target_id == duplicate_id:
                new_source = primary_id if edge.source_id == duplicate_id else edge.source_id
                new_target = primary_id if edge.target_id == duplicate_id else edge.target_id
                if new_source != new_target:
                    edges_to_add.append(
                        {
                            "source_id": new_source,
                            "target_id": new_target,
                            "type": edge.edge_type,
                            "weight": edge.weight,
                            "properties": edge.metadata,
                        }
                    )
                    edges_updated += 1
            else:
                retained_edges.append(edge)

        graph.edges = retained_edges
        graph._adjacency.pop(duplicate_id, None)
        for adjacency in graph._adjacency.values():
            adjacency[:] = [edge for edge in adjacency if edge.target_id != duplicate_id]
        graph.edge_type_index.clear()
        for edge in graph.edges:
            graph.edge_type_index[edge.edge_type].append(edge)

        old_type = graph.nodes[duplicate_id].node_type
        graph.node_type_index.get(old_type, set()).discard(duplicate_id)
        del graph.nodes[duplicate_id]
        removed.append(duplicate_id)

        if edges_to_add:
            graph.add_edges(edges_to_add)

    if removed:
        session.rebuild_search_index()
    return {"merged_into": primary_id, "removed_ids": removed, "edges_updated": edges_updated}
