"""Workspace graph session adapter for Explorer HTTP (wraps ``basis.services.graph.projection.GraphSession``)."""

from __future__ import annotations

import base64
import json
import threading
from datetime import datetime
from typing import Any, Iterator

from basis.services.graph.projection.session import GraphSession
from semantica.context.context_graph import _resolve_edge_identity
from semantica.utils.skos import is_skos_hierarchy_edge, validate_skos_hierarchy


def _node_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "to_dict"):
        return raw.to_dict()
    return {
        "id": str(getattr(raw, "node_id", "")),
        "type": str(getattr(raw, "node_type", "entity")),
        "content": getattr(raw, "content", None),
        "properties": dict(getattr(raw, "properties", {}) or {}),
    }


def _edge_payload(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "to_dict"):
        return raw.to_dict()
    return {
        "id": getattr(raw, "edge_id", None),
        "source": getattr(raw, "source_id", ""),
        "target": getattr(raw, "target_id", ""),
        "type": getattr(raw, "edge_type", "related_to"),
        "weight": getattr(raw, "weight", 1.0),
        "properties": dict(getattr(raw, "properties", {}) or {}),
    }


class BasisGraphSession:
    """Explorer-compatible session API over ``basis.services.graph.projection.GraphSession``."""

    def __init__(self, basis: GraphSession) -> None:
        self._basis = basis
        self.graph = basis.graph
        self._lock = threading.RLock()
        self._path_finder: Any = None
        self._link_predictor: Any = None
        self._similarity: Any = None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _encode_cursor(value: str) -> str:
        return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> str | None:
        if not cursor:
            return None
        try:
            return base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        except Exception:
            return None

    @staticmethod
    def _apply_cursor(items: list[str], start_after: str | None) -> int:
        if not start_after:
            return 0
        for index, item in enumerate(items):
            if item == start_after:
                return index + 1
        return 0

    @staticmethod
    def _node_matches_search(node: dict[str, Any], search: str | None) -> bool:
        if not search:
            return True
        query = search.lower().strip()
        haystacks = [
            str(node.get("id", "")),
            str(node.get("type", "")),
            str(node.get("content", "")),
            json.dumps(node.get("properties", {}), default=str),
        ]
        return any(query in haystack.lower() for haystack in haystacks)

    def normalize_node(self, node: Any) -> dict[str, Any]:
        payload = _node_payload(node)
        meta: dict[str, Any] = {}
        meta.update(payload.get("metadata", {}) or {})
        meta.update(payload.get("properties", {}) or {})

        content = payload.get("content")
        if content is None:
            content = (
                meta.get("content")
                or meta.get("text")
                or meta.get("label")
                or meta.get("name")
                or payload.get("label")
                or payload.get("name")
                or payload.get("id", "")
            )

        valid_from = payload.get("valid_from", meta.get("valid_from"))
        valid_until = payload.get("valid_until", meta.get("valid_until"))

        properties = dict(meta)
        properties.setdefault("content", content)
        if valid_from is not None:
            properties["valid_from"] = valid_from
        if valid_until is not None:
            properties["valid_until"] = valid_until

        return {
            "id": str(payload.get("id", "")),
            "type": str(payload.get("type", "entity")),
            "content": str(content or ""),
            "properties": properties,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }

    def normalize_edge(self, edge: Any) -> dict[str, Any]:
        payload = _edge_payload(edge)
        meta: dict[str, Any] = {}
        meta.update(payload.get("metadata", {}) or {})
        meta.update(payload.get("properties", {}) or {})

        valid_from = payload.get("valid_from", meta.get("valid_from"))
        valid_until = payload.get("valid_until", meta.get("valid_until"))
        weight = self._coerce_float(payload.get("weight"))
        if weight is None:
            weight = 1.0

        properties = dict(meta)
        if valid_from is not None:
            properties["valid_from"] = valid_from
        if valid_until is not None:
            properties["valid_until"] = valid_until

        edge_id, family_id = _resolve_edge_identity(
            source_id=str(payload.get("source", payload.get("source_id", ""))),
            target_id=str(payload.get("target", payload.get("target_id", ""))),
            edge_type=str(payload.get("type", "related_to")),
            weight=weight,
            metadata=properties,
            valid_from=valid_from,
            valid_until=valid_until,
            edge_id=(
                payload.get("id")
                or payload.get("edge_id")
                or meta.get("id")
                or meta.get("edge_id")
            ),
            family_id=(
                payload.get("familyId")
                or payload.get("family_id")
                or meta.get("familyId")
                or meta.get("family_id")
            ),
        )

        return {
            "id": edge_id,
            "familyId": family_id,
            "source": str(payload.get("source", payload.get("source_id", ""))),
            "target": str(payload.get("target", payload.get("target_id", ""))),
            "type": str(payload.get("type", "related_to")),
            "weight": weight,
            "properties": properties,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        with self._lock:
            raw = self.graph.find_node(node_id)
        if raw is None:
            return None
        return self.normalize_node(raw)

    def paginate_nodes(
        self,
        node_type: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
        cursor: str | None = None,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> tuple[list[dict[str, Any]], int, str | None]:
        del bbox  # spatial filter not used on Basis adapter yet
        with self._lock:
            if node_type:
                source_ids = self.graph.node_type_index.get(node_type, set())
            else:
                source_ids = self.graph.nodes.keys()
            node_ids = sorted(
                (node_id for node_id in source_ids if node_id is not None),
                key=lambda value: str(value),
            )

            filtered_ids: list[str] = []
            normalized_by_id: dict[str, dict[str, Any]] = {}
            for node_id in node_ids:
                raw = self.graph.find_node(node_id)
                if raw is None:
                    continue
                normalized = self.normalize_node(raw)
                if not self._node_matches_search(normalized, search):
                    continue
                filtered_ids.append(node_id)
                normalized_by_id[node_id] = normalized

        total = len(filtered_ids)
        start_index = skip
        decoded_cursor = self._decode_cursor(cursor)
        if decoded_cursor:
            start_index = self._apply_cursor(filtered_ids, decoded_cursor)

        page_ids = filtered_ids[start_index : start_index + limit]
        next_cursor = None
        if start_index + limit < total and page_ids:
            next_cursor = self._encode_cursor(page_ids[-1])

        return [normalized_by_id[node_id] for node_id in page_ids], total, next_cursor

    def get_nodes(
        self,
        node_type: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        page, total, _ = self.paginate_nodes(
            node_type=node_type,
            search=search,
            skip=skip,
            limit=limit,
        )
        return page, total

    def iter_nodes(self, node_type: str | None = None) -> Iterator[dict[str, Any]]:
        with self._lock:
            source_ids = (
                self.graph.node_type_index.get(node_type, set())
                if node_type
                else self.graph.nodes.keys()
            )
            node_ids = sorted(
                (node_id for node_id in source_ids if node_id is not None),
                key=lambda value: str(value),
            )
        for node_id in node_ids:
            with self._lock:
                raw = self.graph.find_node(node_id)
            if raw is None:
                continue
            yield self.normalize_node(raw)

    def iter_edges(self, edge_type: str | None = None) -> Iterator[dict[str, Any]]:
        with self._lock:
            raw_edges = self.graph.find_edges(edge_type=edge_type)
        for edge in raw_edges:
            normalized = self.normalize_edge(edge)
            if not normalized["source"] or not normalized["target"]:
                continue
            yield normalized

    def paginate_edges(
        self,
        edge_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
        skip: int = 0,
        limit: int = 100,
        cursor: str | None = None,
    ) -> tuple[list[dict[str, Any]], int, str | None]:
        with self._lock:
            raw_edges = self.graph.find_edges(edge_type=edge_type)

        normalized_edges: list[dict[str, Any]] = []
        keys: list[str] = []
        for edge in raw_edges:
            normalized = self.normalize_edge(edge)
            if not normalized["source"] or not normalized["target"]:
                continue
            if source and normalized["source"] != source:
                continue
            if target and normalized["target"] != target:
                continue
            edge_key = str(normalized["id"])
            normalized_edges.append(normalized)
            keys.append(edge_key)

        ordered = sorted(zip(keys, normalized_edges), key=lambda item: item[0])
        ordered_keys = [key for key, _ in ordered]
        ordered_edges = [edge for _, edge in ordered]

        total = len(ordered_edges)
        start_index = skip
        decoded_cursor = self._decode_cursor(cursor)
        if decoded_cursor:
            start_index = self._apply_cursor(ordered_keys, decoded_cursor)

        page_edges = ordered_edges[start_index : start_index + limit]
        next_cursor = None
        if start_index + limit < total and page_edges:
            next_cursor = self._encode_cursor(str(page_edges[-1]["id"]))

        return page_edges, total, next_cursor

    def get_edges(
        self,
        edge_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        page, total, _ = self.paginate_edges(
            edge_type=edge_type,
            source=source,
            target=target,
            skip=skip,
            limit=limit,
        )
        return page, total

    def get_neighbors(self, node_id: str, depth: int = 1) -> list[dict[str, Any]]:
        with self._lock:
            return self.graph.get_neighbors(node_id, hops=depth)

    def get_raw_counts(self) -> tuple[int, int]:
        with self._lock:
            return len(self.graph.nodes), len(self.graph.edges)

    def search(
        self,
        query: str,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        del filters
        q = query.strip().lower()
        if not q:
            return []
        results: list[dict[str, Any]] = []
        for node in self.iter_nodes():
            haystacks = [
                str(node.get("id", "")),
                str(node.get("content", "")),
                json.dumps(node.get("properties", {}), default=str),
            ]
            if any(q in text.lower() for text in haystacks):
                results.append({"node": node, "score": 1.0})
            if len(results) >= limit:
                break
        return results[:limit]

    def get_temporal_bounds(self) -> dict[str, str | None]:
        min_valid_from: datetime | None = None
        max_valid_until: datetime | None = None

        def _coerce_datetime(value: Any) -> datetime | None:
            if value is None:
                return None
            text = str(value).strip().replace("Z", "+00:00")
            if not text:
                return None
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
            return parsed

        for node in self.iter_nodes():
            valid_from = _coerce_datetime(node.get("valid_from"))
            valid_until = _coerce_datetime(node.get("valid_until"))
            if valid_from is not None and (min_valid_from is None or valid_from < min_valid_from):
                min_valid_from = valid_from
            if valid_until is not None and (
                max_valid_until is None or valid_until > max_valid_until
            ):
                max_valid_until = valid_until

        return {
            "min": min_valid_from.isoformat() if min_valid_from is not None else None,
            "max": max_valid_until.isoformat() if max_valid_until is not None else None,
        }

    def get_active_nodes(
        self, at_time: datetime | None = None, node_type: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            nodes = self.graph.find_active_nodes(node_type=node_type, at_time=at_time)
        return [self.normalize_node(node) for node in nodes]

    def build_graph_dict(self, node_ids: list | None = None) -> dict:
        nodes, _ = self.get_nodes(skip=0, limit=999_999)
        edges, _ = self.get_edges(skip=0, limit=999_999)

        if node_ids:
            id_set = set(node_ids)
            nodes = [node for node in nodes if node.get("id") in id_set]
            edges = [
                edge
                for edge in edges
                if edge.get("source") in id_set and edge.get("target") in id_set
            ]

        return {
            "entities": [
                {
                    "id": node.get("id"),
                    "type": node.get("type", "entity"),
                    "text": node.get("content", node.get("id", "")),
                    "metadata": node.get("properties", {}),
                }
                for node in nodes
            ],
            "relationships": [
                {
                    "id": edge.get("id"),
                    "familyId": edge.get("familyId"),
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "type": edge.get("type", "related_to"),
                    "weight": edge.get("weight", 1.0),
                    "metadata": edge.get("properties", {}),
                }
                for edge in edges
            ],
        }

    def validate_skos_hierarchy(self, edges: list[dict[str, Any]]) -> None:
        hierarchy_edges = [edge for edge in edges if is_skos_hierarchy_edge(edge)]
        if not hierarchy_edges:
            return
        existing_edges = [
            edge for edge in self.graph.find_edges() if is_skos_hierarchy_edge(edge)
        ]
        validate_skos_hierarchy(hierarchy_edges, existing_edges)

    def add_nodes_and_edges(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> tuple[int, int]:
        with self._lock:
            self.validate_skos_hierarchy(edges)
            nodes_added = self.graph.add_nodes(nodes)
            edges_added = self.graph.add_edges(edges)
        return nodes_added, edges_added

    def add_nodes(self, nodes: list[dict[str, Any]]) -> int:
        with self._lock:
            return self.graph.add_nodes(nodes)

    def add_node(
        self,
        node_id: str,
        node_type: str,
        content: str | None = None,
        **properties: Any,
    ) -> bool:
        return self._basis.add_node(node_id, node_type, content=content, **properties)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str = "related_to",
        weight: float = 1.0,
        **properties: Any,
    ) -> bool:
        return self._basis.add_edge(
            source_id,
            target_id,
            edge_type,
            weight=weight,
            **properties,
        )

    def rebuild_search_index(self) -> None:
        return None

    @property
    def path_finder(self) -> Any:
        with self._lock:
            if self._path_finder is None:
                try:
                    from semantica.kg import PathFinder

                    self._path_finder = PathFinder()
                except ImportError:
                    pass
            return self._path_finder

    @property
    def link_predictor(self) -> Any:
        with self._lock:
            if self._link_predictor is None:
                try:
                    from semantica.kg import LinkPredictor

                    self._link_predictor = LinkPredictor()
                except ImportError:
                    pass
            return self._link_predictor

    @property
    def similarity(self) -> Any:
        with self._lock:
            if self._similarity is None:
                try:
                    from semantica.kg import SimilarityCalculator

                    self._similarity = SimilarityCalculator()
                except ImportError:
                    pass
            return self._similarity

    def build_nx_graph(self) -> Any:
        import networkx as nx

        graph = nx.Graph()
        for node in self.iter_nodes():
            graph.add_node(node["id"])
        for edge in self.iter_edges():
            source = edge["source"]
            target = edge["target"]
            weight = float(edge.get("weight", 1.0) or 1.0)
            if graph.has_edge(source, target):
                existing = graph.get_edge_data(source, target)
                if existing is not None:
                    weight = min(weight, existing.get("weight", weight))
            graph.add_edge(source, target, weight=weight)
        return graph
