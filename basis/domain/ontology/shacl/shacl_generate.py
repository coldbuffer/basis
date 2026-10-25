"""SHACL generation from ontology schema subgraph (no Explorer route handlers)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from basis.domain.ontology.browse.analysis_graph import load_ontology_analysis_graph
from basis.domain.ontology.hub.catalog import (
    _entry_field,
    _ontology_entities,
    resolve_registry_entry,
)
from basis.domain.ontology.shacl.shacl_support import (
    basic_shacl_turtle,
    ontology_dict_from_nodes,
    summarize_shacl_shapes,
)
from basis.domain.errors import AdminError

logger = logging.getLogger(__name__)


def _shape_rows(shapes: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for shape in shapes:
        if hasattr(shape, "model_dump"):
            rows.append(shape.model_dump())
        elif isinstance(shape, dict):
            rows.append(shape)
    return rows


def generated_shacl_for_uri(
    session: Any,
    registry: dict[str, Any],
    uri: str,
    *,
    quality_tier: str = "strict",
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    entry = resolve_registry_entry(registry, session, uri)

    name = _entry_field(entry, "name", uri)
    if nodes is None or edges is None:
        nodes, edges = load_ontology_analysis_graph(session, registry, uri)
    entities = _ontology_entities(nodes, uri)
    ontology_dict = ontology_dict_from_nodes(uri, name, entities, edges)

    try:
        from semantica.ontology import OntologyEngine

        shacl_turtle = OntologyEngine().to_shacl(
            ontology_dict,
            format="turtle",
            quality_tier=quality_tier,
            validate_output=False,
        )
    except Exception as exc:
        logger.debug("OntologyEngine.to_shacl unavailable; using basic generator: %s", exc)
        shacl_turtle = basic_shacl_turtle(uri, name, entities)

    return shacl_turtle, _shape_rows(summarize_shacl_shapes(shacl_turtle))


def generate_shacl(
    session: Any,
    registry: dict[str, Any],
    *,
    uri: str,
    quality_tier: str = "strict",
) -> dict[str, Any]:
    shacl_turtle, shapes = generated_shacl_for_uri(
        session,
        registry,
        uri,
        quality_tier=quality_tier,
    )
    return {
        "uri": uri,
        "shacl_turtle": shacl_turtle,
        "shape_count": len(shapes),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def list_shacl_shapes(
    session: Any,
    registry: dict[str, Any],
    *,
    uri: str,
    shacl_turtle_override: str | None = None,
) -> dict[str, Any]:
    if shacl_turtle_override and str(shacl_turtle_override).strip():
        turtle = str(shacl_turtle_override).strip()
        shapes = _shape_rows(summarize_shacl_shapes(turtle))
        return {
            "uri": uri,
            "shapes": shapes,
            "shacl_turtle": turtle,
            "source": "saved",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    shacl_turtle, shapes = generated_shacl_for_uri(session, registry, uri)
    return {
        "uri": uri,
        "shapes": shapes,
        "shacl_turtle": shacl_turtle,
        "source": "generated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
