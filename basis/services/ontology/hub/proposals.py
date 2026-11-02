"""Ontology change proposals lifecycle and SHACL preview."""

from __future__ import annotations


# ── proposal_shacl.py ──
"""SHACL pre-validation for ontology proposals (no Semantica engine store required)."""


import asyncio
from typing import Any

from basis.services.ontology.shacl.shacl_generate import generated_shacl_for_uri
from basis.services.ontology.shacl.shacl_validate import validate_shacl


def _map_shacl_result(result: dict[str, Any]) -> dict[str, Any]:
    status = str(result.get("status") or "unknown")
    if status == "ok":
        return {
            "status": "validated",
            "conforms": bool(result.get("conforms", True)),
            "violations": list(result.get("violations") or []),
            "message": result.get("message"),
        }
    if status == "unavailable":
        return {
            "status": "skipped",
            "reason": result.get("message") or "SHACL validation unavailable",
        }
    return {
        "status": "error" if status == "error" else status,
        "conforms": bool(result.get("conforms", False)),
        "violations": list(result.get("violations") or []),
        "error": result.get("message"),
    }


def validate_proposal_shacl(
    session: Any,
    registry: dict[str, Any] | None,
    ontology_uri: str,
) -> dict[str, Any]:
    uri = str(ontology_uri or "").strip()
    if not uri:
        return {"status": "skipped", "reason": "missing_ontology_uri"}
    if not registry:
        return {"status": "skipped", "reason": "missing_registry"}

    try:
        shacl_turtle, _ = generated_shacl_for_uri(session, registry, uri)
    except Exception as exc:
        return {"status": "error", "error": f"SHACL generation failed: {exc}"}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    try:
        if loop is not None and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    asyncio.run,
                    validate_shacl(session, registry, uri=uri, shacl_turtle=shacl_turtle),
                ).result()
        else:
            result = asyncio.run(
                validate_shacl(session, registry, uri=uri, shacl_turtle=shacl_turtle)
            )
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

    return _map_shacl_result(result)

# ── proposal_lifecycle.py ──
"""Submit and publish ontology change proposals (semantica core, no Explorer routes)."""


import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from basis.services.ontology.hub.draft_apply import structure_change_summary
from basis.services.ontology.persistence.proposal_store import _get_field, _set_field
from basis.services.ontology.hub.registry_scope import ensure_ontology_registry_on_publish
from basis.services.ontology.hub.schema_sync import apply_ontology_diff_to_session
from basis.services.errors import AdminError

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


def _session_store(session: Any) -> Any:
    return session.graph.store if hasattr(session.graph, "store") else None


def submit_proposal(
    session: Any,
    drafts: dict[str, Any],
    proposals: dict[str, Any],
    body: Any,
    registry: dict[str, Any] | None = None,
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
            shacl_validation = validate_proposal_shacl(
                session,
                registry,
                str(body.ontology_uri),
            )

        structure_summary = structure_change_summary(diff)
        impact_analysis = {
            "diff": diff_result,
            "validation_results": validation_results,
            "class_adds": len(_diff_list(diff, "added_classes")),
            "class_removals": len(_diff_list(diff, "removed_classes")),
            "property_changes": len(_diff_list(diff, "added_properties"))
            + len(_diff_list(diff, "removed_properties")),
            "restriction_changes": len(_diff_list(diff, "added_restrictions"))
            + len(_diff_list(diff, "removed_restrictions")),
            **structure_summary,
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
        from basis.services.ontology.models import ProposalResponse

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
    registry: dict[str, Any] | None = None,
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

        from basis.services.ontology.models import VersionEntry

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

    applied = apply_ontology_diff_to_session(session, ontology_uri, diff)
    nodes_added = int(applied.get("nodes_added", 0))
    edges_added = int(applied.get("edges_added", 0))
    nodes_removed = int(applied.get("nodes_removed", 0))
    edges_removed = int(applied.get("edges_removed", 0))

    _set_field(proposal, "state", "published")
    _set_field(proposal, "updated_at", datetime.now(timezone.utc).isoformat())

    registry_meta: dict[str, Any] | None = None
    if registry is not None:
        from basis.services.ontology.hub.registry_scope import _registry_key

        reg_key = _registry_key(registry, ontology_uri) or ontology_uri
        entry = registry.get(reg_key)
        if isinstance(entry, dict):
            entry["version"] = version_str
        elif entry is not None:
            _set_field(entry, "version", version_str)
        registry_meta = ensure_ontology_registry_on_publish(
            session,
            registry,
            ontology_uri,
            proposal=proposal,
            draft=draft,
        )

    payload: dict[str, Any] = {
        "status": "published",
        "proposal_id": proposal_id,
        "version": version_str,
        "nodes_added": nodes_added,
        "edges_added": edges_added,
        "nodes_removed": nodes_removed,
        "edges_removed": edges_removed,
    }
    if registry_meta is not None:
        payload["registry"] = registry_meta
    return payload
