"""Graph export (JSON, CSV, RDF, GraphML)."""

from __future__ import annotations

import csv
import io
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from basis.services.errors import AdminError

logger = logging.getLogger(__name__)

_RDF_FORMATS: dict[str, str] = {
    "ttl": "turtle",
    "turtle": "turtle",
    "nt": "ntriples",
    "ntriples": "ntriples",
    "n-triples": "ntriples",
    "xml": "rdfxml",
    "rdfxml": "rdfxml",
    "rdf-xml": "rdfxml",
    "json-ld": "jsonld",
    "jsonld": "jsonld",
}

_RDF_MEDIA_TYPES: dict[str, tuple[str, str]] = {
    "turtle": ("text/turtle", "ttl"),
    "ntriples": ("application/n-triples", "nt"),
    "rdfxml": ("application/rdf+xml", "rdf"),
    "jsonld": ("application/ld+json", "jsonld"),
}


def export_graph(
    session: Any,
    *,
    format: str = "json",
    node_ids: list[str] | None = None,
) -> tuple[str, str, str]:
    """Return (content, media_type, file extension)."""
    fmt = format.lower()
    graph_dict = session.build_graph_dict(node_ids)

    if fmt == "json":
        content = json.dumps(graph_dict, indent=2, default=str)
        return content, "application/json", "json"

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["kind", "id", "familyId", "type", "content", "source", "target", "weight"])
        for node in graph_dict.get("entities", []):
            writer.writerow(
                ["node", node.get("id"), "", node.get("type"), node.get("text"), "", "", ""]
            )
        for edge in graph_dict.get("relationships", []):
            writer.writerow(
                [
                    "edge",
                    edge.get("id"),
                    edge.get("familyId"),
                    edge.get("type"),
                    "",
                    edge.get("source"),
                    edge.get("target"),
                    edge.get("metadata", {}).get("weight", edge.get("weight", "")),
                ]
            )
        return output.getvalue(), "text/csv", "csv"

    if fmt in _RDF_FORMATS:
        try:
            from semantica.export import RDFExporter
            from semantica.utils.exceptions import ValidationError
        except ImportError as exc:
            raise AdminError(503, "graph_runtime_unavailable", f"RDF export unavailable: {exc}") from exc
        try:
            content = RDFExporter().export_to_rdf(graph_dict, format=_RDF_FORMATS[fmt])
        except ValidationError as exc:
            raise AdminError(422, "validation_error", f"RDF export failed: {exc}") from exc
        except Exception as exc:
            logger.exception("RDF export failed unexpectedly")
            raise AdminError(500, "export_failed", f"RDF export error: {exc}") from exc
        media_type, extension = _RDF_MEDIA_TYPES[_RDF_FORMATS[fmt]]
        return content, media_type, extension

    if fmt == "graphml":
        try:
            from semantica.export import GraphExporter
            from semantica.utils.exceptions import ValidationError
        except ImportError as exc:
            raise AdminError(503, "graph_runtime_unavailable", f"GraphML export unavailable: {exc}") from exc
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir) / "export.graphml"
                exporter = GraphExporter(format="graphml")
                exporter.export(graph_dict, file_path=tmp_path)
                content = tmp_path.read_text(encoding="utf-8")
        except ValidationError as exc:
            raise AdminError(422, "validation_error", f"GraphML export failed: {exc}") from exc
        except Exception as exc:
            logger.exception("GraphML export failed unexpectedly")
            raise AdminError(500, "export_failed", f"GraphML export error: {exc}") from exc
        return content, "application/xml", "graphml"

    supported = sorted({"json", "csv", "graphml"} | set(_RDF_FORMATS))
    raise AdminError(
        422,
        "validation_error",
        f"Unsupported export format '{fmt}'. Supported: {', '.join(supported)}",
    )
