"""SHACL validation for mapped ledger assertions → governance review items."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.conflict.policy import (
    CONFLICT_SCHEMA_VERSION,
    build_property_mapping_index,
    resolve_predicate_policy,
)
from basis.domain.knowledge.conflict.shacl_shapes import per_subject_functional_shapes_turtle
from basis.domain.knowledge.conflict.turtle import (
    assertions_to_data_graph_turtle,
    build_mapped_assertions,
    entity_id_from_node_iri,
)
from basis.domain.knowledge.conflict.scan_context import ConflictScanContext
from basis.domain.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

SHACL_VIOLATION_KIND = "shacl_violation"
SHACL_VIOLATION_SUBJECT_TYPE = "shacl_focus"
CONFLICT_TYPE_SHACL = "shacl_violation"
DETECTOR_L2_SHACL = "l2_shacl_max_count"
DETECTOR_L3_HUB = "l3_hub_shacl"
DETECTOR_SHACL = "shacl"

_PATH_FROM_MESSAGE = re.compile(r"->\s*(<([^>]+)>|(\S+))")


def _functional_predicate_iris(
    rows: list[dict[str, Any]],
    mapping_index: dict[str, dict[str, Any]],
) -> set[str]:
    iris: set[str] = set()
    for row in rows:
        policy = resolve_predicate_policy(str(row.get("surface_phrase") or ""), mapping_index)
        if policy.get("allows_multiple_objects"):
            continue
        iri = policy.get("predicate_iri")
        if iri:
            iris.add(str(iri))
    return iris


def _validate_with_pyshacl(data_turtle: str, shacl_turtle: str) -> list[dict[str, Any]]:
    try:
        from pyshacl import validate
        from rdflib.namespace import RDF, SH
    except ImportError:
        logger.debug("pyshacl unavailable; skipping SHACL conflict scan")
        return []

    data_bytes = data_turtle.encode("utf-8")
    shacl_bytes = shacl_turtle.encode("utf-8")
    try:
        conforms, report_graph, _report_text = validate(
            data_graph=data_bytes,
            shacl_graph=shacl_bytes,
            data_graph_format="turtle",
            shacl_graph_format="turtle",
            inference="none",
            advanced=True,
        )
    except Exception as exc:
        logger.debug("SHACL validation failed: %s", exc)
        return []

    if conforms:
        return []

    violations: list[dict[str, Any]] = []
    for result in report_graph.subjects(predicate=RDF.type, object=SH.ValidationResult):
        severity = report_graph.value(result, SH.resultSeverity)
        severity_text = str(severity or "").lower()
        if "violation" not in severity_text:
            continue
        focus = report_graph.value(result, SH.focusNode)
        path = report_graph.value(result, SH.resultPath)
        message = report_graph.value(result, SH.resultMessage)
        shape = report_graph.value(result, SH.sourceShape)
        focus_str = str(focus) if focus is not None else None
        path_str = str(path) if path is not None else None
        if not path_str and message:
            match = _PATH_FROM_MESSAGE.search(str(message))
            if match:
                path_str = match.group(2) or match.group(3)
        violations.append(
            {
                "focus_node": focus_str,
                "result_path": path_str,
                "message": str(message or "SHACL violation"),
                "source_shape": str(shape) if shape is not None else None,
                "severity": "Violation",
            }
        )
    return violations


def _ledger_mapped_data_turtle(
    knowledge: KnowledgeStore,
    workspace_id: str,
) -> tuple[str, list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    rows = knowledge.list_active_statements(workspace_id)
    mapping_index = build_property_mapping_index(
        knowledge.list_mappings(workspace_id, status="confirmed", limit=500)
    )
    assertions = build_mapped_assertions(rows, mapping_index)
    data_turtle = assertions_to_data_graph_turtle(assertions)
    return data_turtle, rows, mapping_index, assertions


def _combined_shacl_turtle(
    knowledge: KnowledgeStore,
    workspace_id: str,
    assertions: list[dict[str, Any]],
    functional_iris: set[str],
    scan_ctx: ConflictScanContext | None,
) -> tuple[str, str, str | None]:
    hub_turtle = ""
    ontology_uri: str | None = None
    if scan_ctx is not None:
        from basis.domain.knowledge.conflict.hub_shacl import hub_shacl_turtle_for_scan

        hub_turtle, ontology_uri = hub_shacl_turtle_for_scan(knowledge, workspace_id, scan_ctx)
    if hub_turtle.strip():
        return hub_turtle, DETECTOR_L3_HUB, ontology_uri
    synth = per_subject_functional_shapes_turtle(assertions, functional_iris) if functional_iris else ""
    return synth, DETECTOR_SHACL if synth.strip() else DETECTOR_L2_SHACL, ontology_uri


def find_shacl_violation_payloads(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    scan_ctx: ConflictScanContext | None = None,
) -> list[dict[str, Any]]:
    data_turtle, rows, mapping_index, assertions = _ledger_mapped_data_turtle(
        knowledge, workspace_id
    )
    functional_iris = _functional_predicate_iris(rows, mapping_index)
    if not assertions:
        return []

    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()

    shacl_turtle, detector, ontology_uri = _combined_shacl_turtle(
        knowledge,
        workspace_id,
        assertions,
        functional_iris,
        scan_ctx,
    )
    if not shacl_turtle.strip():
        return []

    raw_violations = _validate_with_pyshacl(data_turtle, shacl_turtle)

    for item in raw_violations:
        focus = item.get("focus_node")
        path = item.get("result_path")
        message = str(item.get("message") or "")
        subject_id = entity_id_from_node_iri(focus)
        predicate_iri = None
        if path:
            path_clean = str(path).strip().strip("<>")
            if path_clean.startswith("http") or path_clean.startswith("urn:"):
                predicate_iri = path_clean
        dedupe_key = f"{focus}|{path}|{message[:120]}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        fingerprint = hashlib.sha256(dedupe_key.encode()).hexdigest()[:32]
        rule_id = "hub:shacl" if detector == DETECTOR_L3_HUB else "shacl:constraint"
        payloads.append(
            {
                "schema_version": CONFLICT_SCHEMA_VERSION,
                "conflict_type": CONFLICT_TYPE_SHACL,
                "detector": detector,
                "severity": "high" if detector == DETECTOR_L3_HUB else "medium",
                "rule_id": rule_id,
                "ontology_uri": ontology_uri,
                "focus_node": focus,
                "result_path": path,
                "predicate_iri": predicate_iri,
                "subject_id": subject_id,
                "message": message,
                "source_shape": item.get("source_shape"),
                "fingerprint": fingerprint,
            }
        )

    return payloads


def scan_shacl_violations(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    scan_ctx: ConflictScanContext | None = None,
) -> dict[str, Any]:
    created: list[str] = []
    skipped = 0
    hub_created = 0
    for payload in find_shacl_violation_payloads(
        knowledge,
        workspace_id,
        scan_ctx=scan_ctx,
    ):
        subject_id = str(payload.get("fingerprint") or payload.get("focus_node") or "shacl")
        try:
            item = knowledge.create_review_item(
                workspace_id,
                kind=SHACL_VIOLATION_KIND,
                subject_type=SHACL_VIOLATION_SUBJECT_TYPE,
                subject_id=subject_id[:64],
                payload=payload,
                priority=4,
            )
            created.append(item["id"])
            if payload.get("detector") == "l3_hub_shacl":
                hub_created += 1
        except AdminError as exc:
            if exc.code == "review_exists":
                skipped += 1
                continue
            raise
    return {
        "created": len(created),
        "skipped": skipped,
        "item_ids": created,
        "hub_created": hub_created,
    }
