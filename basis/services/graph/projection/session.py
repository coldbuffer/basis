"""In-memory graph session backed by semantica's ContextGraph."""

from __future__ import annotations

from typing import Any


# Workspace projections do not use Node2Vec; disabling avoids a gensim import warning on
# every ContextGraph() when semantica[graph-embeddings] is not installed.
_DEFAULT_CONTEXT_GRAPH_CONFIG = {"node_embeddings": False}


class GraphSession:
    def __init__(self, *, context_graph_config: dict | None = None) -> None:
        from semantica.context import ContextGraph

        config = {**_DEFAULT_CONTEXT_GRAPH_CONFIG, **(context_graph_config or {})}
        self.graph = ContextGraph(config=config)

    def stats(self) -> dict[str, int]:
        return {
            "node_count": len(self.graph.nodes),
            "edge_count": len(self.graph.edges),
        }

    def add_node(
        self,
        node_id: str,
        node_type: str,
        content: str | None = None,
        **properties: Any,
    ) -> bool:
        return self.graph.add_node(node_id, node_type, content=content, **properties)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str = "related_to",
        **properties: Any,
    ) -> bool:
        return self.graph.add_edge(source_id, target_id, edge_type, **properties)
