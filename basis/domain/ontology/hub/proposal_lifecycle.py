"""Submit and publish ontology change proposals (semantica core, no Explorer routes)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from basis.domain.ontology.hub.draft_apply import (
    apply_removals,
    as_draft_mapping,
    materialize_restrictions,
)
from basis.domain.ontology.hub.proposal_store import _get_field, _set_field
from basis.domain.errors import AdminError

logger = logging.getLogger(__name__)


def _diff_object(draft: Any) -> Any:
    return _get_field(draft, "diff", {})


def _diff_list(diff: Any, key: str) -> list[Any]:
    if diff is None:
        return []
    if hasattr(diff, key):
        value = getattr(diff, key)
        return list(value or [])
    if isinstance(diff, dict):
        return list(diff.get(key) or [])
    return []


def _diff_dump(diff: Any) -> dict[str, Any]:
    if hasattr(diff, "model_dump"):
        return diff.model_dump()
    if isinstance(diff, dict):
        return diff
    return {}


def _diff_dict(diff: Any, key: str) -> dict[str, Any]:
    if diff is None:
        return {}
    if hasattr(diff, key):
        value = getattr(diff, key)
        return dict(value or {}) if isinstance(value, dict) else {}
    if isinstance(diff, dict):
        raw = diff.get(key) or {}
        return dict(raw) if isinstance(raw, dict) else {}
    return {}


def _label_for_uri(diff: Any, uri: str, modified_key: str) -> str:
    modified = _diff_dict(diff, modified_key)
    entry = modified.get(uri) or {}
    label = entry.get("label")
    if label is not None and str(label).strip():
        return str(label).strip()
    return _label_from_uri(uri)


def _session_store(session: Any) -> Any:
    return session.graph.store if hasattr(session.graph, "store") else None


def _label_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def submit_proposal(
    session: Any,
    drafts: dict[str, Any],
    proposals: dict[str, Any],
    body: Any,
) -> dict[str, Any]:
    if body.draft_id not in drafts:
        raise AdminError(404, "not_found", "Draft not found.")

    draft = drafts[body.draft_id]
    diff = _diff_object(draft)
    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    impact_analysis: dict[str, Any] = {}
    shacl_validation: dict[str, Any] = {}

    try:
        from semantica.change_management.ontology_version_manager import VersionManager
        from semantica.ontology import OntologyEngine

        base_ontology = {"uri": body.ontology_uri, "classes": [], "properties": []}
        target_ontology = {
            "uri": body.ontology_uri,
            "classes": [{"uri": uri} for uri in _diff_list(diff, "added_classes")],
            "properties": [{"uri": uri} for uri in _diff_list(diff, "added_properties")],
        }

        version_manager = VersionManager(store=_session_store(session))
        diff_result = version_manager.diff_ontologies(base_ontology, target_ontology)

        engine = OntologyEngine(store=_session_store(session))

        validation_results: dict[str, Any] = {}
        try:
            val_res = engine.validate(target_ontology)
            validation_results = {
                "valid": getattr(val_res, "valid", getattr(val_res, "is_valid", False)),
                "consistent": getattr(val_res, "consistent", True),
                "satisfiable": getattr(val_res, "satisfiable", True),
                "errors": getattr(val_res, "errors", []),
                "warnings": getattr(val_res, "warnings", []),
            }
        except Exception as val_exc:
            logger.warning("Validation failed: %s", val_exc)
            validation_results = {"error": str(val_exc)}

        if engine.store:
            try:
                engine.to_shacl(target_ontology, format="turtle")
                all_nodes, _ = session.get_nodes(skip=0, limit=999_999)
                graph_data = {"nodes": all_nodes}
                validation_report = engine.validate_graph(
                    graph_data,
                    ontology=target_ontology,
                    explain=True,
                )
                shacl_validation = {
                    "status": "validated",
                    "conforms": getattr(validation_report, "conforms", True),
                    "violations": [
                        {
                            "message": v.message,
                            "severity": v.severity,
                            "focus_node": v.focus_node,
                        }
                        for v in getattr(validation_report, "violations", [])
                    ],
                }
            except Exception as shacl_exc:
                logger.warning("SHACL pre-validation failed: %s", shacl_exc)
                shacl_validation = {"status": "error", "error": str(shacl_exc)}
        else:
            shacl_validation = {"status": "skipped", "reason": "No store configured"}

        impact_analysis = {
            "diff": diff_result,
            "validation_results": validation_results,
            "class_adds": len(_diff_list(diff, "added_classes")),
            "class_removals": len(_diff_list(diff, "removed_classes")),
            "property_changes": len(_diff_list(diff, "added_properties"))
            + len(_diff_list(diff, "removed_properties")),
            "restriction_changes": len(_diff_list(diff, "added_restrictions"))
            + len(_diff_list(diff, "removed_restrictions")),
        }
    except Exception as exc:
        logger.warning("Impact analysis failed: %s", exc)
        impact_analysis = {"error": str(exc)}
        shacl_validation = {"status": "error", "error": str(exc)}

    record = {
        "proposal_id": proposal_id,
        "draft_id": body.draft_id,
        "ontology_uri": body.ontology_uri,
        "summary": body.summary,
        "author": _get_field(draft, "author"),
        "reviewer": body.reviewer,
        "state": "proposed",
        "impact_analysis": impact_analysis,
        "shacl_validation": shacl_validation,
        "created_at": now,
        "updated_at": now,
        "comments": [],
    }
    try:
        from basis.domain.ontology.hub.hub_models import ProposalResponse

        proposals[proposal_id] = ProposalResponse.model_validate(record)
    except Exception:
        proposals[proposal_id] = record

    if hasattr(proposals[proposal_id], "model_dump"):
        return proposals[proposal_id].model_dump()
    return record


def publish_proposal(
    session: Any,
    proposals: dict[str, Any],
    drafts: dict[str, Any],
    versions: dict[str, list[Any]],
    proposal_id: str,
) -> dict[str, Any]:
    if proposal_id not in proposals:
        raise AdminError(404, "not_found", "Proposal not found.")
    proposal = proposals[proposal_id]

    if _get_field(proposal, "state") != "approved":
        raise AdminError(400, "validation_error", "Only approved proposals can be published.")

    draft_id = _get_field(proposal, "draft_id")
    if draft_id not in drafts:
        raise AdminError(404, "not_found", "Draft not found.")
    draft = drafts[draft_id]
    diff = _diff_object(draft)
    ontology_uri = _get_field(proposal, "ontology_uri")

    ontology_dict = {
        "uri": ontology_uri,
        "classes": [{"uri": uri} for uri in _diff_list(diff, "added_classes")],
        "properties": [{"uri": uri} for uri in _diff_list(diff, "added_properties")],
        "diff": _diff_dump(diff),
    }

    try:
        from semantica.change_management.ontology_version_manager import VersionManager

        version_manager = VersionManager(store=_session_store(session))
        existing_versions = versions.get(ontology_uri, [])
        version_num = len(existing_versions) + 1
        version_str = f"1.{version_num}.0"

        version_manager.create_version(
            version=version_str,
            ontology=ontology_dict,
            changes=[_get_field(proposal, "summary")],
        )

        from basis.domain.ontology.hub.hub_models import VersionEntry

        entry = VersionEntry(
            version_id=version_str,
            ontology_uri=ontology_uri,
            state="published",
            author=_get_field(proposal, "author"),
            date=datetime.now(timezone.utc).isoformat(),
            diff_summary=_diff_dump(diff),
        )
        if ontology_uri not in versions:
            versions[ontology_uri] = []
        versions[ontology_uri].append(entry)
        logger.info("Created version %s for ontology %s", version_str, ontology_uri)
    except AdminError:
        raise
    except Exception as exc:
        logger.warning("VersionManager.create_version failed: %s", exc)
        raise AdminError(500, "internal_error", f"Version creation failed: {exc}") from exc

    nodes_removed, edges_removed = apply_removals(session, diff, diff_list=_diff_list)

    nodes_added = 0
    edges_added = 0

    class_nodes = []
    for class_uri in _diff_list(diff, "added_classes"):
        label = _label_for_uri(diff, class_uri, "modified_classes")
        class_nodes.append(
            {
                "id": class_uri,
                "type": "owl:Class",
                "content": label,
                "properties": {"rdfs:label": label},
            }
        )
    modified_classes = _diff_dict(diff, "modified_classes")
    added_class_set = set(_diff_list(diff, "added_classes"))
    for class_uri, changes in modified_classes.items():
        if class_uri in added_class_set:
            continue
        label = changes.get("label")
        if label is None or not str(label).strip():
            continue
        label_str = str(label).strip()
        class_nodes.append(
            {
                "id": class_uri,
                "type": "owl:Class",
                "content": label_str,
                "properties": {"rdfs:label": label_str},
            }
        )
    if class_nodes:
        nodes_added += session.add_nodes(class_nodes)

    property_nodes = []
    for prop_uri in _diff_list(diff, "added_properties"):
        label = _label_for_uri(diff, prop_uri, "modified_properties")
        property_nodes.append(
            {
                "id": prop_uri,
                "type": "owl:ObjectProperty",
                "content": label,
                "properties": {"rdfs:label": label},
            }
        )
    modified_properties = _diff_dict(diff, "modified_properties")
    added_property_set = set(_diff_list(diff, "added_properties"))
    for prop_uri, changes in modified_properties.items():
        if prop_uri in added_property_set:
            continue
        label = changes.get("label")
        if label is None or not str(label).strip():
            continue
        label_str = str(label).strip()
        property_nodes.append(
            {
                "id": prop_uri,
                "type": "owl:ObjectProperty",
                "content": label_str,
                "properties": {"rdfs:label": label_str},
            }
        )
    if property_nodes:
        nodes_added += session.add_nodes(property_nodes)

    individual_nodes = []
    for ind_uri in _diff_list(diff, "added_individuals"):
        label = _label_from_uri(ind_uri)
        individual_nodes.append(
            {
                "id": ind_uri,
                "type": "owl:NamedIndividual",
                "content": label,
                "properties": {"rdfs:label": label},
            }
        )
    if individual_nodes:
        nodes_added += session.add_nodes(individual_nodes)

    restriction_nodes, restriction_edges = materialize_restrictions(
        ontology_uri,
        _diff_list(diff, "added_restrictions"),
    )
    if restriction_nodes:
        nodes_added += session.add_nodes(restriction_nodes)

    edges_to_add: list[dict[str, Any]] = list(restriction_edges)
    for raw_edge in _diff_list(diff, "added_edges"):
        edge_map = as_draft_mapping(raw_edge)
        source = str(edge_map.get("source", "")).strip()
        target = str(edge_map.get("target", "")).strip()
        edge_type = str(edge_map.get("type", "")).strip()
        if not source or not target or not edge_type:
            continue
        edges_to_add.append(
            {
                "source": source,
                "target": target,
                "type": edge_type,
                "weight": float(edge_map.get("weight", 1.0) or 1.0),
            }
        )

    for raw_axiom in _diff_list(diff, "added_axioms"):
        axiom_map = as_draft_mapping(raw_axiom)
        axiom_type = str(axiom_map.get("type", "")).strip()
        subject = str(axiom_map.get("subject") or axiom_map.get("source") or "").strip()
        object_uri = str(axiom_map.get("object") or axiom_map.get("value") or "").strip()
        if axiom_type == "subClassOf" and subject and object_uri:
            edges_to_add.append(
                {
                    "source": subject,
                    "target": object_uri,
                    "type": "rdfs:subClassOf",
                    "weight": 1.0,
                }
            )

    if edges_to_add:
        _, edges_added = session.add_nodes_and_edges([], edges_to_add)

    _set_field(proposal, "state", "published")
    _set_field(proposal, "updated_at", datetime.now(timezone.utc).isoformat())

    return {
        "status": "published",
        "proposal_id": proposal_id,
        "version": version_str,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "nodes_removed": nodes_removed,
        "edges_removed": edges_removed,
    }
