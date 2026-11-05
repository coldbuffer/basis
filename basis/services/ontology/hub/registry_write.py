"""Ontology registry write operations (create, load, refresh, delete)."""

from __future__ import annotations


# ── registry_write.py ──
"""Registry mutations for Hub ontology management."""


from typing import Any

from basis.services.errors import AdminError


def _entry_enabled(entry: Any) -> bool:
    if isinstance(entry, dict):
        return bool(entry.get("enabled", True))
    return bool(getattr(entry, "enabled", True))


def _set_entry_enabled(entry: Any, enabled: bool) -> None:
    if isinstance(entry, dict):
        entry["enabled"] = enabled
    else:
        entry.enabled = enabled


def remove_ontology(registry: dict[str, Any], ontology_uri: str) -> dict[str, str]:
    if ontology_uri not in registry:
        raise AdminError(404, "not_found", "Ontology not found in registry.")
    del registry[ontology_uri]
    return {"status": "removed", "uri": ontology_uri}


def toggle_ontology(registry: dict[str, Any], ontology_uri: str) -> dict[str, Any]:
    if ontology_uri not in registry:
        raise AdminError(404, "not_found", "Ontology not found in registry.")
    entry = registry[ontology_uri]
    new_enabled = not _entry_enabled(entry)
    _set_entry_enabled(entry, new_enabled)
    return {"uri": ontology_uri, "enabled": new_enabled}

# ── create_write.py ──
"""Create ontology in graph session + workspace registry (no Explorer route handlers)."""


import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from basis.services.errors import AdminError

logger = logging.getLogger(__name__)


def _engine_config(session: Any, provider: str | None, model: str | None) -> dict[str, Any]:
    config: dict[str, Any] = {
        "store": session.graph.store if hasattr(session.graph, "store") else None,
    }
    if provider:
        config["provider"] = provider
    if model:
        config["model"] = model
    return config


def _append_engine_result(
    ns: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    result: dict[str, Any],
) -> None:
    for cls in result.get("classes", []):
        cls_uri = f"{ns}/{cls.get('name', uuid.uuid4().hex[:6])}"
        nodes.append(
            {
                "id": cls_uri,
                "type": "owl:Class",
                "content": cls.get("name", ""),
                "properties": {
                    "rdfs:label": cls.get("name", ""),
                    "rdfs:comment": cls.get("description", ""),
                },
            }
        )

    for prop in result.get("properties", []):
        prop_uri = f"{ns}/{prop.get('name', uuid.uuid4().hex[:6])}"
        nodes.append(
            {
                "id": prop_uri,
                "type": "owl:ObjectProperty",
                "content": prop.get("name", ""),
                "properties": {"rdfs:label": prop.get("name", "")},
            }
        )
        domain = prop.get("domain")
        if domain and str(domain).strip():
            domain_uri = f"{ns}/{domain}"
            edges.append(
                {
                    "source": prop_uri,
                    "target": domain_uri,
                    "type": "rdfs:domain",
                    "weight": 1.0,
                }
            )
        range_val = prop.get("range")
        if range_val and str(range_val).strip():
            range_uri = f"{ns}/{range_val}"
            edges.append(
                {
                    "source": prop_uri,
                    "target": range_uri,
                    "type": "rdfs:range",
                    "weight": 1.0,
                }
            )

    for cls in result.get("classes", []):
        cls_uri = f"{ns}/{cls.get('name', '')}"
        for parent in cls.get("superclasses", []):
            parent_uri = f"{ns}/{parent}"
            edges.append(
                {
                    "source": cls_uri,
                    "target": parent_uri,
                    "type": "rdfs:subClassOf",
                    "weight": 1.0,
                }
            )


def create_ontology(
    session: Any,
    registry: dict[str, Any],
    *,
    namespace: str,
    name: str,
    description: str | None = None,
    tags: list[str] | None = None,
    mode: str = "scratch",
    sample_data: str | None = None,
    schema_text: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    ns = namespace.rstrip("/#")
    onto_uri = f"{ns}#ontology"

    nodes: list[dict[str, Any]] = [
        {
            "id": onto_uri,
            "type": "owl:Ontology",
            "content": name,
            "properties": {
                "rdfs:label": name,
                "rdfs:comment": description or "",
                "namespace": namespace,
            },
        }
    ]
    edges: list[dict[str, Any]] = []

    if mode == "data" and sample_data:
        try:
            from semantica.ontology import OntologyEngine

            engine = OntologyEngine(**_engine_config(session, provider, model))
            result = engine.from_data(sample_data)
            if isinstance(result, dict):
                _append_engine_result(ns, nodes, edges, result)
            logger.info("Generated ontology from sample data with %s nodes, %s edges", len(nodes), len(edges))
        except Exception as exc:
            logger.exception("Failed to generate ontology from sample data")
            raise AdminError(500, "internal_error", f"Ontology generation failed: {exc}") from exc

    elif mode == "text" and schema_text:
        try:
            from semantica.ontology import OntologyEngine

            engine = OntologyEngine(**_engine_config(session, provider, model))
            result = engine.from_text(schema_text, provider=provider, model=model)
            if isinstance(result, dict):
                _append_engine_result(ns, nodes, edges, result)
            logger.info("Generated ontology from text with %s nodes, %s edges", len(nodes), len(edges))
        except Exception as exc:
            logger.exception("Failed to generate ontology from schema text")
            raise AdminError(500, "internal_error", f"Ontology generation failed: {exc}") from exc

    try:
        nodes_added, edges_added = session.add_nodes_and_edges(nodes, edges)
    except ValueError as exc:
        raise AdminError(422, "validation_error", str(exc)) from exc

    registry[onto_uri] = {
        "uri": onto_uri,
        "name": name,
        "description": description,
        "format": "turtle",
        "status": "draft",
        "version": "0.1.0",
        "class_count": sum(1 for n in nodes if n.get("type") == "owl:Class"),
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
        "tags": list(tags or []),
    }

    return {
        "status": "success",
        "uri": onto_uri,
        "name": name,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "format": "turtle",
    }

# ── load_write.py ──
"""Ontology load into graph session + workspace registry (no Explorer route handlers)."""


import logging
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from typing import Any

from basis.services.ontology.hub.catalog import _classify_node_type
from basis.services.ontology.browse.preview_read import detect_format, normalize_format
from basis.services.errors import AdminError

logger = logging.getLogger(__name__)

_INGEST_FORMAT_SUFFIXES: dict[str, str] = {
    "turtle": ".ttl",
    "xml": ".rdf",
    "json-ld": ".jsonld",
    "nt": ".nt",
    "n3": ".n3",
    "trig": ".trig",
    "nquads": ".nq",
}


def _count_entity_types(nodes: list[dict[str, Any]]) -> tuple[int, int, int]:
    classes = concepts = properties = 0
    for node in nodes:
        kind = _classify_node_type(node.get("type", ""))
        if kind == "class":
            classes += 1
        elif kind == "concept":
            concepts += 1
        elif kind == "property":
            properties += 1
    return classes, concepts, properties


def _register_ontology(
    registry: dict[str, Any],
    *,
    ontology_uri: str,
    name: str,
    description: str | None,
    fmt: str,
    version: str | None,
    class_count: int,
    concept_count: int,
    property_count: int,
    tags: list[str] | None,
    source_url: str | None,
) -> None:
    registry[ontology_uri] = {
        "uri": ontology_uri,
        "name": name,
        "description": description,
        "format": fmt,
        "status": "external",
        "version": version or "1.0",
        "class_count": class_count,
        "concept_count": concept_count,
        "property_count": property_count,
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
        "tags": list(tags or []),
        "source_url": source_url,
    }


def _load_response(
    *,
    ontology_uri: str,
    name: str,
    nodes_added: int,
    edges_added: int,
    fmt: str,
) -> dict[str, Any]:
    return {
        "status": "success",
        "uri": ontology_uri,
        "name": name,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "format": fmt,
    }


def _prepare_ingestor_text(content_str: str, fmt: str) -> str:
    if fmt != "xml":
        return content_str
    from basis.services.ontology.io.rdf_parse import expand_literal_internal_entities

    return expand_literal_internal_entities(content_str.encode("utf-8")).decode("utf-8")


def _graph_from_ontology_ingestor(
    content_str: str,
    fmt: str,
    convert_ontology_to_graph: Callable[[dict[str, Any]], tuple[list[Any], list[Any]]],
) -> tuple[list[Any], list[Any], dict[str, Any]]:
    """Parse ontology content with Semantica OntologyIngestor and map it to graph nodes."""
    from semantica.ingest.ontology_ingestor import OntologyIngestor

    suffix = _INGEST_FORMAT_SUFFIXES.get(fmt)
    if suffix is None:
        raise AdminError(422, "validation_error", f"Unsupported ontology format: {fmt}")

    payload = _prepare_ingestor_text(content_str, fmt)
    ingestor = OntologyIngestor()
    with NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as temp_file:
        temp_file.write(payload)
        temp_path = temp_file.name
    try:
        ontology_data = ingestor.ingest_ontology(temp_path, format=fmt)
    except AdminError:
        raise
    except Exception as exc:
        raise AdminError(422, "validation_error", f"Could not parse ontology: {exc}") from exc
    finally:
        try:
            os.unlink(temp_path)
        except OSError as cleanup_exc:
            logger.debug("Failed to remove temporary ontology file: %s", cleanup_exc)

    data = ontology_data.data
    nodes, edges = convert_ontology_to_graph(data)
    return nodes, edges, data


def load_ontology(
    session: Any,
    registry: dict[str, Any],
    *,
    url: str | None,
    content: str | None,
    format: str | None,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    fetch_url_bytes: Callable[[str], bytes],
    convert_ontology_to_graph: Callable[[dict[str, Any]], tuple[list[Any], list[Any]]],
) -> dict[str, Any]:
    if not url and not content:
        raise AdminError(422, "validation_error", "Provide either url or content.")

    if url:
        raw = fetch_url_bytes(url)
        content_str = raw.decode("utf-8", errors="replace")
    else:
        content_str = content or ""

    fmt = normalize_format(format) if format else detect_format(content_str)
    nodes, edges, data = _graph_from_ontology_ingestor(content_str, fmt, convert_ontology_to_graph)

    try:
        nodes_added, edges_added = session.add_nodes_and_edges(nodes, edges)
    except ValueError as exc:
        raise AdminError(422, "validation_error", str(exc)) from exc

    ontology_uri = data.get("uri") or f"temp:{uuid.uuid4().hex[:12]}"
    display_name = name or data.get("name") or "Imported Ontology"
    cc, cn, cp = _count_entity_types(nodes)
    _register_ontology(
        registry,
        ontology_uri=ontology_uri,
        name=display_name,
        description=description or data.get("description"),
        fmt=fmt,
        version=data.get("version", "1.0"),
        class_count=cc,
        concept_count=cn,
        property_count=cp,
        tags=tags,
        source_url=url,
    )
    return _load_response(
        ontology_uri=ontology_uri,
        name=display_name,
        nodes_added=nodes_added,
        edges_added=edges_added,
        fmt=fmt,
    )

# ── refresh_write.py ──
"""Re-fetch ontology content from registry source_url."""


from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from basis.services.errors import AdminError


def _entry_field(entry: Any, key: str, default: Any = None) -> Any:
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _set_loaded_at(entry: Any, value: str) -> None:
    if isinstance(entry, dict):
        entry["loaded_at"] = value
    else:
        entry.loaded_at = value


def refresh_ontology(
    session: Any,
    registry: dict[str, Any],
    ontology_uri: str,
    *,
    fetch_url_bytes: Callable[[str], bytes],
    convert_ontology_to_graph: Callable[[dict[str, Any]], tuple[list[Any], list[Any]]],
) -> dict[str, Any]:
    entry = registry.get(ontology_uri)
    if entry is None:
        raise AdminError(404, "not_found", "Ontology not found in registry.")

    source_url = _entry_field(entry, "source_url")
    if not source_url:
        raise AdminError(422, "validation_error", "No source URL to refresh from.")

    fmt = normalize_format(str(_entry_field(entry, "format", "turtle")))
    raw = fetch_url_bytes(str(source_url))
    content_str = raw.decode("utf-8", errors="replace")
    nodes, edges, _data = _graph_from_ontology_ingestor(content_str, fmt, convert_ontology_to_graph)

    try:
        nodes_added, edges_added = session.add_nodes_and_edges(nodes, edges)
    except ValueError as exc:
        raise AdminError(422, "validation_error", str(exc)) from exc

    _set_loaded_at(entry, datetime.now(timezone.utc).isoformat())

    return {
        "uri": ontology_uri,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
    }
