"""Document nodes stored on the knowledge graph."""

from __future__ import annotations

from typing import Any

from basis.services.graph.projection.session import GraphSession


def list_documents(session: GraphSession) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for node in session.graph.nodes.values():
        if node.node_type != "document":
            continue
        content = node.content or node.properties.get("content") or node.properties.get("text") or ""
        preview = content[:200] if isinstance(content, str) else ""
        docs.append(
            {
                "doc_id": node.node_id,
                "preview": preview,
                "char_count": len(content) if isinstance(content, str) else 0,
            }
        )
    docs.sort(key=lambda item: item["doc_id"])
    return docs
