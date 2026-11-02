"""SHACL validation against ontology data graph (no Explorer route handlers)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from basis.services.ontology.browse.analysis_graph import load_ontology_analysis_graph
from basis.services.ontology.browse.data_graph_read import data_graph_turtle_for_uri
from basis.services.ontology.browse.graph_scope import GraphTruncationError
from basis.services.ontology.shacl.shacl_limits import get_shacl_semaphore
from basis.services.errors import AdminError

_MAX_SHACL_TURTLE_BYTES = int(os.environ.get("SEMANTICA_MAX_SHACL_TURTLE_BYTES", "262144"))
_MAX_SHACL_TRIPLES = int(os.environ.get("SEMANTICA_MAX_SHACL_TRIPLES", "1000"))
_MAX_SHACL_TIMEOUT_SECONDS = float(os.environ.get("SEMANTICA_MAX_SHACL_TIMEOUT", "15.0"))


def _response(
    *,
    uri: str | None,
    conforms: bool,
    status: str,
    message: str,
    violations: list[dict[str, Any]] | None = None,
    report_text: str | None = None,
) -> dict[str, Any]:
    return {
        "uri": uri or "",
        "conforms": conforms,
        "status": status,
        "message": message,
        "violations": violations or [],
        "report_text": report_text,
    }


def _syntax_error_message(shacl_turtle: str) -> str | None:
    """Return an error message for oversize triple count, or raise on bad syntax."""
    try:
        import rdflib
    except ImportError:
        return None

    try:
        graph = rdflib.Graph()
        graph.parse(data=shacl_turtle, format="turtle")
        if len(graph) > _MAX_SHACL_TRIPLES:
            return (
                f"SHACL graph triple count ({len(graph)}) "
                f"exceeds maximum allowed limit ({_MAX_SHACL_TRIPLES}); "
                f"set SEMANTICA_MAX_SHACL_TRIPLES to raise the limit."
            )
    except Exception as exc:
        raise AdminError(422, "validation_error", f"Invalid Turtle syntax: {exc}") from exc
    return None


async def validate_shacl(
    session: Any,
    registry: dict[str, Any],
    *,
    uri: str | None,
    shacl_turtle: str,
) -> dict[str, Any]:
    if not shacl_turtle.strip():
        raise AdminError(422, "validation_error", "SHACL Turtle cannot be empty.")

    shacl_bytes = shacl_turtle.encode("utf-8")
    if len(shacl_bytes) > _MAX_SHACL_TURTLE_BYTES:
        return _response(
            uri=uri,
            conforms=False,
            status="error",
            message=(
                f"SHACL Turtle size ({len(shacl_bytes)} bytes) "
                f"exceeds maximum allowed size ({_MAX_SHACL_TURTLE_BYTES} bytes); "
                f"set SEMANTICA_MAX_SHACL_TURTLE_BYTES to raise the limit."
            ),
        )

    syntax_error = _syntax_error_message(shacl_turtle)
    if syntax_error:
        return _response(uri=uri, conforms=False, status="error", message=syntax_error)

    if not uri:
        return _response(
            uri=uri,
            conforms=False,
            status="unavailable",
            message=(
                "Turtle parsed successfully. "
                "No target ontology URI was provided — "
                "specify 'uri' to execute live SHACL validation against an ontology data graph."
            ),
        )

    try:
        nodes, edges = load_ontology_analysis_graph(session, registry, uri)
        data_graph_turtle = await data_graph_turtle_for_uri(
            registry,
            session,
            uri,
            nodes=nodes,
            edges=edges,
        )
        from semantica.ontology import OntologyEngine

        engine = OntologyEngine()
        semaphore = get_shacl_semaphore()

        async def _run_validation() -> Any:
            async with semaphore:
                return await asyncio.to_thread(
                    engine.validate_graph,
                    data_graph_turtle,
                    shacl=shacl_turtle,
                    data_graph_format="turtle",
                    shacl_format="turtle",
                )

        report = await asyncio.wait_for(_run_validation(), timeout=_MAX_SHACL_TIMEOUT_SECONDS)
    except (asyncio.TimeoutError, TimeoutError):
        return _response(
            uri=uri,
            conforms=False,
            status="error",
            message=(
                f"SHACL validation timed out after {_MAX_SHACL_TIMEOUT_SECONDS} seconds; "
                f"set SEMANTICA_MAX_SHACL_TIMEOUT to raise the timeout."
            ),
        )
    except GraphTruncationError as exc:
        return _response(
            uri=uri,
            conforms=False,
            status="unavailable",
            message=str(exc),
        )
    except ImportError as exc:
        return _response(
            uri=uri,
            conforms=False,
            status="unavailable",
            message=(
                "Turtle parsed successfully. "
                f"Live SHACL validation is unavailable: {exc}"
            ),
        )
    except AdminError:
        raise
    except Exception as exc:
        return _response(
            uri=uri,
            conforms=False,
            status="error",
            message=f"SHACL validation error: {exc}",
        )

    violations: list[dict[str, Any]] = []
    for item in [*report.violations, *report.warnings, *report.infos]:
        violations.append(
            {
                "node": str(item.focus_node) if item.focus_node is not None else None,
                "path": str(item.result_path) if item.result_path is not None else None,
                "severity": str(item.severity or "Violation"),
                "message": str(
                    item.message
                    or item.explanation
                    or f"SHACL constraint violation ({item.constraint}) on {item.focus_node}"
                ),
                "focus_node": str(item.focus_node) if item.focus_node is not None else None,
                "source_shape": str(item.shape) if item.shape is not None else None,
            }
        )

    result_counts: list[str] = []
    if report.violations:
        result_counts.append(f"{len(report.violations)} violation(s)")
    if report.warnings:
        result_counts.append(f"{len(report.warnings)} warning(s)")
    if report.infos:
        result_counts.append(f"{len(report.infos)} info result(s)")
    summary_msg = (
        f"SHACL validation found {', '.join(result_counts)}."
        if result_counts
        else "Graph conforms to SHACL shapes."
    )

    return _response(
        uri=uri,
        conforms=report.conforms,
        status="success",
        message=summary_msg,
        violations=violations,
        report_text=report.raw_report,
    )
