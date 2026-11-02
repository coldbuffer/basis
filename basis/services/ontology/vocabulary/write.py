"""SKOS vocabulary import for workspace Explorer HTTP."""

from __future__ import annotations

import os
from typing import Any

from basis.services.errors import AdminError

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_ALLOWED_EXTENSIONS = frozenset({".ttl", ".rdf", ".owl", ".xml", ".jsonld", ".json-ld", ".json"})


def import_vocabulary(
    session: Any,
    *,
    content: bytes | None = None,
    text: str | None = None,
    filename: str | None = None,
    format: str | None = None,
) -> dict[str, Any]:
    from basis.services.ontology.io.rdf_parse import parse_skos_file

    if content is None and not text:
        raise AdminError(422, "validation_error", "Provide either a vocabulary file or raw RDF text.")

    if content is not None:
        if filename:
            ext = os.path.splitext(filename.lower())[1]
            if ext not in _ALLOWED_EXTENSIONS:
                raise AdminError(
                    422,
                    "validation_error",
                    f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
                )
        if len(content) > _MAX_UPLOAD_BYTES:
            raise AdminError(
                413,
                "payload_too_large",
                f"Upload exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )
    else:
        encoded = text.encode("utf-8")
        if len(encoded) > _MAX_UPLOAD_BYTES:
            raise AdminError(
                413,
                "payload_too_large",
                f"Text payload exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )
        content = encoded

    parse_format = (format or "").strip().lower() or None
    if parse_format is None:
        if filename:
            lower_name = filename.lower()
            if lower_name.endswith((".rdf", ".owl", ".xml")):
                parse_format = "xml"
            elif lower_name.endswith((".jsonld", ".json-ld", ".json")):
                parse_format = "json-ld"
            else:
                parse_format = "turtle"
        else:
            parse_format = "turtle"

    try:
        nodes, edges = parse_skos_file(content, parse_format)
    except ValueError as exc:
        raise AdminError(422, "validation_error", str(exc)) from exc

    try:
        nodes_added, edges_added = session.add_nodes_and_edges(nodes, edges)
    except ValueError as exc:
        raise AdminError(422, "validation_error", str(exc)) from exc

    return {
        "status": "success",
        "filename": filename,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "format": parse_format,
    }
