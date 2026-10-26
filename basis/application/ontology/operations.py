"""Ontology hub application operations (registry, graph, drafts, proposals)."""

from __future__ import annotations

from typing import Any

from basis.application.kernel import WorkspaceCoreContext, require_workspace_editor
from basis.application.ontology.hub_access import OntologyHubAccess, run_ontology_hub
from basis.domain.ontology.browse.graph_read import (
    get_ontology_graph as get_ontology_graph_read,
    search_entities as search_entities_read,
)
from basis.domain.ontology.hub.catalog import list_registry
from basis.domain.ontology.hub.draft_store import get_draft as get_draft_sync
from basis.domain.ontology.hub.draft_store import list_drafts as list_drafts_sync
from basis.domain.ontology.hub.draft_store import save_draft as save_draft_sync
from basis.domain.knowledge.services.alerts_emit import emit_governance_proposal_proposed_alert
from basis.domain.ontology.hub.hub_models import (
    CommentRequest,
    DraftDiff,
    DraftRequest,
    ProposalRequest,
    VersionCompareRequest,
    VersionRestoreRequest,
)
from basis.domain.ontology.hub.version_restore import build_restore_draft_diff
from basis.domain.ontology.hub.proposal_lifecycle import (
    publish_proposal as publish_proposal_sync,
    submit_proposal as submit_proposal_sync,
)
from basis.domain.ontology.hub.version_store import (
    compare_versions as compare_versions_sync,
    list_versions as list_versions_sync,
)
from basis.domain.ontology.hub.proposal_store import (
    add_proposal_comment as add_proposal_comment_sync,
    approve_proposal as approve_proposal_sync,
    get_proposal as get_proposal_sync,
    list_proposals as list_proposals_sync,
    reject_proposal as reject_proposal_sync,
)


def _author(ctx: WorkspaceCoreContext) -> str:
    return str(ctx.user.email or ctx.user.id or "agent")


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {}


def op_list_ontology_registry(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        from basis.domain.ontology.hub.registry_ensure import backfill_registry_from_versions
        from basis.domain.ontology.hub.schema_sync import sync_enabled_ontology_schema

        if backfill_registry_from_versions(hub.registry, hub.versions):
            hub.persist_hub()
        if sync_enabled_ontology_schema(hub.graph_session, hub.registry, hub.versions).get("repaired"):
            hub.persist_hub()
        entries = list_registry(
            hub.registry,
            hub.graph_session,
            versions=hub.versions,
            q=str(args.get("q") or "").strip() or None,
            status=str(args.get("status") or "").strip() or None,
            format=str(args.get("format") or "").strip() or None,
        )
        return {"registry": entries}

    return run_ontology_hub(ctx, _run)


def op_get_ontology_graph(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    uri = str(args.get("uri") or "").strip()
    if not uri:
        return {"error": "uri is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        from basis.domain.ontology.hub.schema_sync import ensure_ontology_schema_materialized

        if ensure_ontology_schema_materialized(
            hub.graph_session, hub.registry, hub.versions, uri
        ).get("repaired"):
            hub.persist_hub()
        payload = get_ontology_graph_read(
            hub.graph_session,
            hub.registry,
            uri=uri,
            versions=hub.versions,
        )
        return {"graph": payload}

    return run_ontology_hub(ctx, _run)


def op_search_ontology_entities(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("q") or args.get("query") or "").strip()
    if not query:
        return {"error": "q is required"}
    entity_type = str(args.get("entity_type") or "").strip() or None
    limit = min(max(1, int(args.get("limit", 50))), 200)

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        results = search_entities_read(
            hub.graph_session,
            q=query,
            entity_type=entity_type,
            limit=limit,
        )
        return {"q": query, "results": results}

    return run_ontology_hub(ctx, _run)


def op_save_ontology_draft(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    ontology_uri = str(args.get("ontology_uri") or "").strip()
    if not ontology_uri:
        return {"error": "ontology_uri is required"}
    diff_raw = args.get("diff")
    if not isinstance(diff_raw, dict):
        return {"error": "diff (object) is required"}
    summary = str(args.get("summary") or "MCP ontology draft").strip()

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        body = DraftRequest(
            ontology_uri=ontology_uri,
            diff=DraftDiff.model_validate(diff_raw),
            author=_author(ctx),
            summary=summary,
        )
        saved = save_draft_sync(hub.drafts, body)
        hub.persist_hub()
        if hasattr(saved, "model_dump"):
            return {"draft": saved.model_dump()}
        return {"draft": saved}

    return run_ontology_hub(ctx, _run)


def op_list_ontology_drafts(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    ontology_uri = str(args.get("ontology_uri") or "").strip()
    if not ontology_uri:
        return {"error": "ontology_uri is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        rows = list_drafts_sync(hub.drafts, ontology_uri)
        return {"drafts": rows}

    return run_ontology_hub(ctx, _run)


def op_get_ontology_draft(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    draft_id = str(args.get("draft_id") or "").strip()
    if not draft_id:
        return {"error": "draft_id is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        return {"draft": get_draft_sync(hub.drafts, draft_id)}

    return run_ontology_hub(ctx, _run)


def op_submit_ontology_proposal(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    draft_id = str(args.get("draft_id") or "").strip()
    ontology_uri = str(args.get("ontology_uri") or "").strip()
    summary = str(args.get("summary") or "MCP ontology proposal").strip()
    if not draft_id or not ontology_uri:
        return {"error": "draft_id and ontology_uri are required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        body = ProposalRequest(
            draft_id=draft_id,
            ontology_uri=ontology_uri,
            summary=summary,
            reviewer=str(args.get("reviewer") or "").strip() or None,
        )
        result = submit_proposal_sync(
            hub.graph_session,
            hub.drafts,
            hub.proposals,
            body,
            hub.registry,
        )
        hub.persist_hub()
        data = _as_dict(result)
        proposal_id = str(data.get("proposal_id") or "").strip()
        if proposal_id:
            emit_governance_proposal_proposed_alert(
                ctx.knowledge,
                ctx.workspace.id,
                proposal_id=proposal_id,
                message=str(data.get("summary") or "").strip()
                or f"Ontology proposal {proposal_id} awaiting review",
                detail={
                    "proposal_id": proposal_id,
                    "ontology_uri": data.get("ontology_uri"),
                    "state": data.get("state"),
                },
            )
        return {"proposal": data or result}

    return run_ontology_hub(ctx, _run)


def op_list_ontology_proposals(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    ontology_uri = str(args.get("ontology_uri") or "").strip() or None
    state = str(args.get("state") or "").strip() or None

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        rows = list_proposals_sync(hub.proposals, ontology_uri=ontology_uri, state=state)
        return {"proposals": rows}

    return run_ontology_hub(ctx, _run)


def op_get_ontology_proposal(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    proposal_id = str(args.get("proposal_id") or "").strip()
    if not proposal_id:
        return {"error": "proposal_id is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        return {"proposal": get_proposal_sync(hub.proposals, proposal_id)}

    return run_ontology_hub(ctx, _run)


def op_approve_ontology_proposal(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    proposal_id = str(args.get("proposal_id") or "").strip()
    if not proposal_id:
        return {"error": "proposal_id is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        result = approve_proposal_sync(hub.proposals, proposal_id)
        hub.persist_hub()
        return result

    return run_ontology_hub(ctx, _run)


def op_reject_ontology_proposal(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    proposal_id = str(args.get("proposal_id") or "").strip()
    if not proposal_id:
        return {"error": "proposal_id is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        result = reject_proposal_sync(hub.proposals, proposal_id)
        hub.persist_hub()
        return result

    return run_ontology_hub(ctx, _run)


def op_publish_ontology_proposal(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    proposal_id = str(args.get("proposal_id") or "").strip()
    if not proposal_id:
        return {"error": "proposal_id is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        result = publish_proposal_sync(
            hub.graph_session,
            hub.proposals,
            hub.drafts,
            hub.versions,
            proposal_id,
            hub.registry,
        )
        hub.persist_hub()
        data = _as_dict(result)
        return data if data else {"result": result}

    return run_ontology_hub(ctx, _run)


def op_comment_ontology_proposal(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    proposal_id = str(args.get("proposal_id") or "").strip()
    element_uri = str(args.get("element_uri") or "").strip()
    text = str(args.get("text") or "").strip()
    if not proposal_id or not element_uri or not text:
        return {"error": "proposal_id, element_uri, and text are required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        body = CommentRequest(
            element_uri=element_uri,
            text=text,
            author=_author(ctx),
        )
        result = add_proposal_comment_sync(hub.proposals, proposal_id, body)
        hub.persist_hub()
        return result

    return run_ontology_hub(ctx, _run)


def op_list_ontology_versions(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    ontology_uri = str(args.get("ontology_uri") or "").strip()
    if not ontology_uri:
        return {"error": "ontology_uri is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        rows = list_versions_sync(hub.versions, ontology_uri)
        return {"versions": rows}

    return run_ontology_hub(ctx, _run)


def op_compare_ontology_versions(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    ontology_uri = str(args.get("ontology_uri") or "").strip()
    version1 = str(args.get("version1") or "").strip()
    version2 = str(args.get("version2") or "").strip()
    if not ontology_uri or not version1 or not version2:
        return {"error": "ontology_uri, version1, and version2 are required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        body = VersionCompareRequest(version1=version1, version2=version2)
        result = compare_versions_sync(hub.graph_session, hub.versions, ontology_uri, body)
        hub.persist_hub()
        data = _as_dict(result)
        return data if data else {"comparison": result}

    return run_ontology_hub(ctx, _run)


def op_restore_ontology_version_draft(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    ontology_uri = str(args.get("ontology_uri") or "").strip()
    target_version = str(args.get("target_version") or "").strip()
    if not ontology_uri or not target_version:
        return {"error": "ontology_uri and target_version are required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        entries = list(hub.versions.get(ontology_uri) or [])
        if not entries:
            return {"error": "not_found", "message": "No versions for ontology"}
        try:
            built = build_restore_draft_diff(entries, target_version)
        except KeyError:
            return {"error": "not_found", "message": "Target version not found"}
        except ValueError as exc:
            return {"error": "validation_error", "message": str(exc)}
        if built.get("already_at_target"):
            return {"restore": built, "draft": None}
        summary = (
            str(args.get("summary") or "").strip()
            or f"Restore to {target_version} from {built.get('head_version')}"
        )
        body = DraftRequest(
            ontology_uri=ontology_uri,
            diff=DraftDiff.model_validate(built.get("diff") or {}),
            author=_author(ctx),
            summary=summary,
        )
        saved = save_draft_sync(hub.drafts, body)
        hub.persist_hub()
        draft_payload = saved.model_dump() if hasattr(saved, "model_dump") else saved
        return {"restore": built, "draft": draft_payload}

    return run_ontology_hub(ctx, _run)


def op_toggle_ontology(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    require_workspace_editor(ctx)
    ontology_uri = str(args.get("ontology_uri") or "").strip()
    if not ontology_uri:
        return {"error": "ontology_uri is required"}

    def _run(hub: OntologyHubAccess) -> dict[str, Any]:
        from basis.domain.ontology.hub.registry_write import toggle_ontology

        result = toggle_ontology(hub.registry, ontology_uri)
        hub.persist_hub()
        return result

    payload = run_ontology_hub(ctx, _run)
    if payload.get("error"):
        return payload
    if ctx.rebuild_projection is not None:
        payload["projection"] = ctx.rebuild_projection()
    return payload
