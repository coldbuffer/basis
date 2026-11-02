"""Graph import writes (review-approved)."""

from __future__ import annotations

import csv
import io
import json
import os
import re
from typing import Any

from basis.services.errors import AdminError

_IMPORT_MAX_BYTES = 50 * 1024 * 1024
_ALLOWED_IMPORT_EXTENSIONS = frozenset({".json", ".csv"})
_UNSAFE_ID_CHARS = re.compile(r'[\r\n\x00"\\]')
_MAX_IMPORT_NODE_ID_LEN = 512


def _sanitize_import_node_id(raw: object) -> str:
    if raw is None:
        return ""
    cleaned = _UNSAFE_ID_CHARS.sub("_", str(raw).strip())
    if len(cleaned) > _MAX_IMPORT_NODE_ID_LEN:
        raise AdminError(
            422,
            "validation_error",
            f"Node ID exceeds maximum length of {_MAX_IMPORT_NODE_ID_LEN} characters.",
        )
    return cleaned


def _import_response(nodes_added: int, edges_added: int, message: str = "Import successful") -> dict[str, Any]:
    return {
        "status": "success",
        "message": message,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "nodes_imported": nodes_added,
        "edges_imported": edges_added,
    }


def import_graph_file(session: Any, *, filename: str, content: bytes) -> dict[str, Any]:
    lower_name = (filename or "").lower()
    ext = os.path.splitext(lower_name)[1]
    if ext not in _ALLOWED_IMPORT_EXTENSIONS:
        raise AdminError(
            422,
            "validation_error",
            f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_IMPORT_EXTENSIONS)}",
        )
    if len(content) > _IMPORT_MAX_BYTES:
        raise AdminError(
            413,
            "payload_too_large",
            f"Upload exceeds the {_IMPORT_MAX_BYTES // (1024 * 1024)} MB limit.",
        )

    if lower_name.endswith(".json"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AdminError(422, "validation_error", f"Invalid JSON file: {exc}") from exc

        if isinstance(data, list):
            if data and any(
                key in data[0]
                for key in {"source", "source_id", "target", "target_id", "START_ID", "END_ID"}
            ):
                raw_nodes = []
                raw_edges = data
            else:
                raw_nodes = data
                raw_edges = []
        elif isinstance(data, dict):
            raw_nodes = data.get("nodes", data.get("entities", []))
            raw_edges = data.get("edges", data.get("relationships", []))
        else:
            raise AdminError(422, "validation_error", "JSON import expects an object or array payload")

        nodes = []
        for raw_node in raw_nodes:
            if "properties" in raw_node:
                safe_node_id = _sanitize_import_node_id(
                    raw_node.get("id", raw_node.get("_id", raw_node.get("node_id", "")))
                )
                nodes.append({**raw_node, "id": safe_node_id})
                continue
            metadata = raw_node.get("metadata", {}) or {}
            nodes.append(
                {
                    "id": _sanitize_import_node_id(
                        raw_node.get("id", raw_node.get("_id", raw_node.get("node_id", "")))
                    ),
                    "type": raw_node.get("type", "entity"),
                    "properties": {
                        "content": raw_node.get("text", raw_node.get("content", raw_node.get("id", ""))),
                        **metadata,
                    },
                }
            )

        edges = []
        for raw_edge in raw_edges:
            source = (
                raw_edge.get("source")
                or raw_edge.get("source_id")
                or raw_edge.get("start")
                or raw_edge.get("start_id")
                or raw_edge.get("START_ID")
            )
            target = (
                raw_edge.get("target")
                or raw_edge.get("target_id")
                or raw_edge.get("end")
                or raw_edge.get("end_id")
                or raw_edge.get("END_ID")
            )
            if not source or not target:
                continue
            edge_properties = raw_edge.get("metadata", raw_edge.get("properties", {})) or {}
            edges.append(
                {
                    "id": raw_edge.get("id", raw_edge.get("edge_id")),
                    "familyId": raw_edge.get("familyId", raw_edge.get("family_id")),
                    "source_id": _sanitize_import_node_id(source),
                    "target_id": _sanitize_import_node_id(target),
                    "type": raw_edge.get("type", raw_edge.get("relationship", "related_to")),
                    "weight": float(raw_edge.get("weight", 1.0)),
                    "properties": edge_properties,
                    "valid_from": raw_edge.get("valid_from", edge_properties.get("valid_from")),
                    "valid_until": raw_edge.get("valid_until", edge_properties.get("valid_until")),
                }
            )

        try:
            nodes_added, edges_added = session.add_nodes_and_edges(nodes, edges)
        except ValueError as exc:
            raise AdminError(422, "validation_error", str(exc)) from exc
        return _import_response(nodes_added, edges_added)

    if lower_name.endswith(".csv"):
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise AdminError(422, "validation_error", "CSV file must be UTF-8 encoded") from exc

        reader = csv.DictReader(io.StringIO(decoded))
        nodes = []
        edges = []
        for row in reader:
            source = row.get("source") or row.get("source_id") or row.get(":START_ID") or row.get("START_ID")
            target = row.get("target") or row.get("target_id") or row.get(":END_ID") or row.get("END_ID")
            node_id = row.get("id") or row.get("node_id") or row.get(":ID") or row.get("_id") or row.get("ID")

            if source and target:
                edge_props = {
                    key: value
                    for key, value in row.items()
                    if key
                    not in {
                        "id",
                        "edge_id",
                        "familyId",
                        "family_id",
                        "source",
                        "source_id",
                        "target",
                        "target_id",
                        "type",
                        "relationship",
                        "weight",
                        ":START_ID",
                        "START_ID",
                        ":END_ID",
                        "END_ID",
                        ":TYPE",
                    }
                }
                edges.append(
                    {
                        "id": row.get("id") or row.get("edge_id"),
                        "familyId": row.get("familyId") or row.get("family_id"),
                        "source_id": _sanitize_import_node_id(source),
                        "target_id": _sanitize_import_node_id(target),
                        "type": row.get("type") or row.get("relationship") or row.get(":TYPE") or "related_to",
                        "weight": float(row.get("weight", 1.0) or 1.0),
                        "properties": edge_props,
                    }
                )
            elif node_id:
                node_props = {
                    key: value
                    for key, value in row.items()
                    if key not in {"id", "node_id", "type", "label", ":ID", "_id", "ID", ":LABEL"}
                }
                nodes.append(
                    {
                        "id": _sanitize_import_node_id(node_id),
                        "type": row.get("type") or row.get("label") or row.get(":LABEL") or "entity",
                        "properties": node_props,
                    }
                )

        if not nodes and not edges:
            raise AdminError(
                422,
                "validation_error",
                "No valid nodes or edges could be parsed from the CSV payload.",
            )

        try:
            nodes_added, edges_added = session.add_nodes_and_edges(nodes, edges)
        except ValueError as exc:
            raise AdminError(422, "validation_error", str(exc)) from exc
        return _import_response(nodes_added, edges_added)

    raise AdminError(
        422,
        "validation_error",
        f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_IMPORT_EXTENSIONS)}",
    )
