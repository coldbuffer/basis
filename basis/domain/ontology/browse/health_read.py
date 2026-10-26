"""Ontology health report (Basis implementation)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from basis.domain.ontology.browse.analysis_graph import load_ontology_analysis_graph
from basis.domain.ontology.hub.catalog import (
    _MAX_ANALYSIS_NODES,
    _classify_node_type,
    _entry_field,
    _node_label,
    _ontology_entities,
    resolve_registry_entry,
)
from basis.domain.ontology.browse.data_graph_read import data_graph_turtle_for_uri
from basis.domain.ontology.browse.graph_scope import GraphTruncationError
from basis.domain.ontology.shacl.shacl_generate import generated_shacl_for_uri
from basis.domain.errors import AdminError

logger = logging.getLogger(__name__)


def _entity_description(node: dict[str, Any]) -> str | None:
    props = node.get("properties", {})
    return (
        props.get("rdfs:comment")
        or props.get("skos:definition")
        or props.get("definition")
        or props.get("description")
    )


def _entity_definition(node: dict[str, Any]) -> str | None:
    props = node.get("properties", {})
    return props.get("skos:definition") or props.get("definition")


def _alignment_field(item: Any, key: str) -> str | None:
    if isinstance(item, dict):
        value = item.get(key)
    else:
        value = getattr(item, key, None)
    return str(value) if value else None


def _dimension(
    *,
    key: str,
    label: str,
    score: float,
    status: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "score": round(score, 1),
        "status": status,
        "detail": detail,
    }


def _issue(
    *,
    issue_id: str,
    severity: str,
    category: str,
    message: str,
    action: str | None = None,
    entity_uri: str | None = None,
    entity_label: str | None = None,
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "severity": severity,
        "category": category,
        "entity_uri": entity_uri,
        "entity_label": entity_label,
        "message": message,
        "action": action,
    }


async def ontology_health(
    session: Any,
    registry: dict[str, Any],
    alignments: dict[str, Any],
    *,
    uri: str,
) -> dict[str, Any]:
    if not uri or not str(uri).strip():
        raise AdminError(422, "validation_error", "Query parameter uri is required.")

    entry = resolve_registry_entry(registry, session, uri)

    name = _entry_field(entry, "name", uri)
    entry_version = _entry_field(entry, "version")
    entry_source_url = _entry_field(entry, "source_url")

    nodes, total_nodes = await asyncio.to_thread(
        session.get_nodes,
        skip=0,
        limit=_MAX_ANALYSIS_NODES,
    )
    edges, _ = await asyncio.to_thread(
        session.get_edges,
        skip=0,
        limit=_MAX_ANALYSIS_NODES,
    )
    if total_nodes > _MAX_ANALYSIS_NODES:
        logger.warning(
            "ontology-health: graph has %d nodes; analysis capped at %d.",
            total_nodes,
            _MAX_ANALYSIS_NODES,
        )

    entities = _ontology_entities(nodes, uri)
    classes = [node for node in entities if _classify_node_type(node.get("type", "")) == "class"]
    properties = [node for node in entities if _classify_node_type(node.get("type", "")) == "property"]
    assessed = classes + properties

    issues: list[dict[str, Any]] = []
    total = max(len(assessed), 1)
    with_label = sum(1 for node in assessed if _node_label(node))
    with_comment = sum(1 for node in assessed if _entity_description(node))
    with_definition = sum(1 for node in assessed if _entity_definition(node))
    completeness_score = ((with_label + with_comment + with_definition) / (total * 3)) * 100

    for node in assessed:
        label = _node_label(node)
        if not _entity_description(node):
            issues.append(
                _issue(
                    issue_id=f"doc:{node.get('id')}",
                    severity="warning",
                    category="Documentation",
                    entity_uri=node.get("id"),
                    entity_label=label,
                    message=f"{label} is missing a comment or definition.",
                    action="Add documentation in Editor.",
                )
            )

    property_range_edges = {
        edge.get("source") for edge in edges if edge.get("type") == "rdfs:range"
    }
    missing_range = [node for node in properties if node.get("id") not in property_range_edges]
    for node in missing_range[:25]:
        issues.append(
            _issue(
                issue_id=f"range:{node.get('id')}",
                severity="info",
                category="Consistency",
                entity_uri=node.get("id"),
                entity_label=_node_label(node),
                message="Property has no explicit rdfs:range.",
                action="Review property range in Editor.",
            )
        )

    consistency_score = max(0.0, 100.0 - (len(missing_range) / max(len(properties), 1)) * 60.0)

    assessed_ids = {node.get("id") for node in assessed if node.get("id")}
    aligned_sources: set[str] = set()
    for item in alignments.values():
        source = _alignment_field(item, "source_uri")
        target = _alignment_field(item, "target_uri")
        if source and source in assessed_ids:
            aligned_sources.add(source)
        if target and target in assessed_ids:
            aligned_sources.add(target)
    alignment_score = (len(aligned_sources) / total) * 100
    if assessed and not aligned_sources:
        issues.append(
            _issue(
                issue_id=f"alignment:{uri}",
                severity="warning",
                category="Alignment",
                message="No cross-ontology alignments are recorded for local classes or properties.",
                action="Review suggested alignments.",
                entity_uri=uri,
                entity_label=str(_entry_field(entry, "name", uri)),
            )
        )

    documentation_score = ((with_comment / total) * 80.0) + (
        20.0 if entry_version or entry_source_url else 0.0
    )

    try:
        health_nodes, health_edges = load_ontology_analysis_graph(session, registry, uri)
        shacl_turtle, _ = generated_shacl_for_uri(
            session,
            registry,
            uri,
            nodes=health_nodes,
            edges=health_edges,
        )
        data_graph_turtle = await data_graph_turtle_for_uri(
            registry,
            session,
            uri,
            nodes=health_nodes,
            edges=health_edges,
        )
        from semantica.ontology import OntologyEngine

        engine = OntologyEngine()
        report = await asyncio.to_thread(
            engine.validate_graph,
            data_graph_turtle,
            shacl=shacl_turtle,
            data_graph_format="turtle",
            shacl_format="turtle",
        )
        warning_count = len(report.warnings)
        if not report.conforms:
            shacl_score = max(0.0, 100.0 - (report.violation_count * 20.0))
        elif warning_count:
            shacl_score = max(0.0, 100.0 - (warning_count * 5.0))
        else:
            shacl_score = 100.0
        shacl_status = "ok" if report.conforms and not warning_count else "warning"
        detail_parts: list[str] = []
        if not report.conforms:
            detail_parts.append(f"{report.violation_count} SHACL violation(s)")
        if warning_count:
            detail_parts.append(f"{warning_count} SHACL warning(s)")
        shacl_detail = (
            "Graph conforms to all generated SHACL constraints."
            if not detail_parts
            else f"Graph has {', '.join(detail_parts)}."
        )
        shacl_dimension = _dimension(
            key="shacl",
            label="SHACL Conformance",
            score=shacl_score,
            status=shacl_status,
            detail=shacl_detail,
        )
    except GraphTruncationError as exc:
        shacl_dimension = _dimension(
            key="shacl",
            label="SHACL Conformance",
            score=0.0,
            status="critical",
            detail=str(exc),
        )
    except ImportError:
        shacl_dimension = _dimension(
            key="shacl",
            label="SHACL Conformance",
            score=0.0,
            status="unavailable",
            detail=(
                "Live SHACL validation is available in SHACL Studio when optional "
                "validation dependencies are installed."
            ),
        )
    except Exception as exc:
        shacl_dimension = _dimension(
            key="shacl",
            label="SHACL Conformance",
            score=0.0,
            status="critical",
            detail=f"Live SHACL validation failed: {exc}",
        )

    dimensions = [
        _dimension(
            key="completeness",
            label="Completeness",
            score=completeness_score,
            status="ok" if completeness_score >= 80 else "warning",
            detail=f"{with_label}/{total} labeled, {with_comment}/{total} documented, {with_definition}/{total} defined.",
        ),
        _dimension(
            key="consistency",
            label="Consistency",
            score=consistency_score,
            status="ok" if consistency_score >= 80 else "warning",
            detail=f"{len(missing_range)} properties are missing explicit ranges.",
        ),
        shacl_dimension,
        _dimension(
            key="alignment",
            label="Alignment Coverage",
            score=alignment_score,
            status="ok" if alignment_score >= 50 else "warning",
            detail=f"{len(aligned_sources)}/{total} classes or properties have an alignment.",
        ),
        _dimension(
            key="documentation",
            label="Documentation",
            score=documentation_score,
            status="ok" if documentation_score >= 75 else "warning",
            detail="Measures comments plus source/version metadata.",
        ),
    ]
    scoreable = [dim for dim in dimensions if dim["status"] != "unavailable"]
    total_score = sum(dim["score"] for dim in scoreable) / max(len(scoreable), 1)

    return {
        "uri": uri,
        "name": name,
        "total_score": round(total_score, 1),
        "dimensions": dimensions,
        "issues": issues[:100],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
