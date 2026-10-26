"""Ontology hub drafts, proposals, and version routes."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request

from basis.domain.tenancy.admin.store import AdminStore, User
from basis.interface.http.shared.deps import (
    get_current_user,
    graph_runtime_for,
    get_workspace_for_role,
    get_knowledge_store,
    get_store,
    save_graph,
)
from basis.application.ontology import operations as ontology_ops
from basis.domain.ontology.hub.scoped_state import OntologyHubState
from basis.domain.ontology.hub.hub_models import (
    CommentRequest,
    DraftRequest,
    ProposalRequest,
    VersionCompareRequest,
    VersionRestoreRequest,
)
from basis.domain.graph.governance.decision import (
    maybe_emit_governance_tripped_for_admin_error,
)
from basis.domain.errors import AdminError
from basis.interface.http.workspace.ontology.ontology_application_http import run_ontology_operation
from basis.interface.http.workspace.ontology.ontology_hub_support import (
    audit_ontology_graph_write,
    governance_alert_from_proposal_result,
    min_role,
    ontology_session,
)


def register_ontology_hub_governance_routes(router: APIRouter) -> None:
    async def _ont_17_save_draft(
        workspace_id: str,
        body: DraftRequest,
        request: Request,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Save Draft. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_save_ontology_draft,
            body.model_dump(),
            http_method="PATCH",
            require_editor=True,
        )
        return payload.get("draft", payload)

    router.add_api_route("/{workspace_id}/ontology/draft", _ont_17_save_draft, methods=["PATCH"], name="_ont_17_save_draft")

    async def _ont_18_list_drafts(
        workspace_id: str,
        request: Request,
        ontology_uri: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
List Drafts. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_list_ontology_drafts,
            {"ontology_uri": ontology_uri},
            http_method="GET",
        )
        return payload.get("drafts", [])

    router.add_api_route("/{workspace_id}/ontology/drafts/{ontology_uri:path}", _ont_18_list_drafts, methods=["GET"], name="_ont_18_list_drafts")

    async def _ont_19_get_draft(
        workspace_id: str,
        request: Request,
        draft_id: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Get Draft. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_get_ontology_draft,
            {"draft_id": draft_id},
            http_method="GET",
        )
        return payload.get("draft", payload)

    router.add_api_route("/{workspace_id}/ontology/draft/{draft_id}", _ont_19_get_draft, methods=["GET"], name="_ont_19_get_draft")

    async def _ont_20_submit_proposal(
        workspace_id: str,
        request: Request,
        body: ProposalRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Submit Proposal. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_submit_ontology_proposal,
            body.model_dump(),
            http_method="POST",
            require_editor=True,
        )
        return payload.get("proposal", payload)

    router.add_api_route("/{workspace_id}/ontology/propose", _ont_20_submit_proposal, methods=["POST"], name="_ont_20_submit_proposal")

    async def _ont_21_list_proposals(
        workspace_id: str,
        request: Request,
        ontology_uri: Optional[str] = Query(None),
        state: Optional[str] = Query(None),
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
List Proposals. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        args: dict[str, Any] = {}
        if ontology_uri:
            args["ontology_uri"] = ontology_uri
        if state:
            args["state"] = state
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_list_ontology_proposals,
            args,
            http_method="GET",
        )
        return payload.get("proposals", [])

    router.add_api_route("/{workspace_id}/ontology/proposals", _ont_21_list_proposals, methods=["GET"], name="_ont_21_list_proposals")

    async def _ont_22_get_proposal(
        workspace_id: str,
        request: Request,
        proposal_id: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Get Proposal. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_get_ontology_proposal,
            {"proposal_id": proposal_id},
            http_method="GET",
        )
        return payload.get("proposal", payload)

    router.add_api_route("/{workspace_id}/ontology/proposals/{proposal_id}", _ont_22_get_proposal, methods=["GET"], name="_ont_22_get_proposal")

    async def _ont_23_approve_proposal(
        workspace_id: str,
        request: Request,
        proposal_id: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Approve Proposal. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        knowledge = get_knowledge_store(request)
        try:
            result = await run_ontology_operation(
                request,
                workspace_id,
                user,
                store,
                ontology_ops.op_approve_ontology_proposal,
                {"proposal_id": proposal_id},
                http_method="POST",
                require_editor=True,
            )
        except AdminError as exc:
            maybe_emit_governance_tripped_for_admin_error(
                workspace_id,
                knowledge,
                exc,
                detail={"proposal_id": proposal_id, "source": "ontology_approve"},
                actor_id=user.id,
                runtime_loader=lambda: graph_runtime_for(request, workspace_id),
                persist_graph=lambda kid: save_graph(request, kid),
            )
            raise
        governance_alert_from_proposal_result(
            request,
            workspace_id,
            knowledge,
            proposal_id,
            result,
            actor_id=user.id,
        )
        return result

    router.add_api_route("/{workspace_id}/ontology/proposals/{proposal_id}/approve", _ont_23_approve_proposal, methods=["POST"], name="_ont_23_approve_proposal")

    async def _ont_24_reject_proposal(
        workspace_id: str,
        request: Request,
        proposal_id: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Reject Proposal. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        return await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_reject_ontology_proposal,
            {"proposal_id": proposal_id},
            http_method="POST",
            require_editor=True,
        )

    router.add_api_route("/{workspace_id}/ontology/proposals/{proposal_id}/reject", _ont_24_reject_proposal, methods=["POST"], name="_ont_24_reject_proposal")

    async def _ont_25_publish_proposal(
        workspace_id: str,
        request: Request,
        proposal_id: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Publish Proposal. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        knowledge = get_knowledge_store(request)
        try:
            result = await run_ontology_operation(
                request,
                workspace_id,
                user,
                store,
                ontology_ops.op_publish_ontology_proposal,
                {"proposal_id": proposal_id},
                http_method="POST",
                require_editor=True,
            )
        except AdminError as exc:
            maybe_emit_governance_tripped_for_admin_error(
                workspace_id,
                knowledge,
                exc,
                detail={"proposal_id": proposal_id, "source": "ontology_publish"},
                actor_id=user.id,
                runtime_loader=lambda: graph_runtime_for(request, workspace_id),
                persist_graph=lambda kid: save_graph(request, kid),
            )
            raise
        governance_alert_from_proposal_result(
            request,
            workspace_id,
            knowledge,
            proposal_id,
            result,
            actor_id=user.id,
        )
        audit_ontology_graph_write(
            store,
            user,
            workspace_id,
            "workspace.graph.ontology_publish",
            {"proposal_id": proposal_id, **result},
        )
        return result

    router.add_api_route("/{workspace_id}/ontology/proposals/{proposal_id}/publish", _ont_25_publish_proposal, methods=["POST"], name="_ont_25_publish_proposal")

    async def _ont_26_add_comment(
        workspace_id: str,
        request: Request,
        proposal_id: str,
        body: CommentRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Add Comment. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        args = {
            "proposal_id": proposal_id,
            "element_uri": body.element_uri,
            "text": body.text,
        }
        return await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_comment_ontology_proposal,
            args,
            http_method="POST",
            require_editor=True,
        )

    router.add_api_route("/{workspace_id}/ontology/proposals/{proposal_id}/comment", _ont_26_add_comment, methods=["POST"], name="_ont_26_add_comment")

    async def _ont_27_list_versions(
        workspace_id: str,
        request: Request,
        ontology_uri: str,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
List Versions. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        payload = await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_list_ontology_versions,
            {"ontology_uri": ontology_uri},
            http_method="GET",
        )
        return payload.get("versions", [])

    router.add_api_route("/{workspace_id}/ontology/versions/{ontology_uri:path}", _ont_27_list_versions, methods=["GET"], name="_ont_27_list_versions")

    async def _ont_28_compare_versions(
        workspace_id: str,
        request: Request,
        ontology_uri: str,
        body: VersionCompareRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Compare Versions. Ontology hub (SKOS, alignments) via workspace graph session. Requires workspace membership (session) or workspace API token with read/write scope. All paths are scoped to `{workspace_id}`.
        """
        return await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_compare_ontology_versions,
            {
                "ontology_uri": ontology_uri,
                "version1": body.version1,
                "version2": body.version2,
            },
            http_method="POST",
            require_editor=True,
        )

    router.add_api_route("/{workspace_id}/ontology/versions/{ontology_uri:path}/compare", _ont_28_compare_versions, methods=["POST"], name="_ont_28_compare_versions")

    async def _ont_29_restore_version_draft(
        workspace_id: str,
        request: Request,
        ontology_uri: str,
        body: VersionRestoreRequest,
        user: User = Depends(get_current_user),
        store: AdminStore = Depends(get_store),
    ) -> Any:
        """
Restore Version Draft. Build an editor draft that moves the published head back toward ``target_version`` (governance review required to publish). Requires workspace editor.
        """
        return await run_ontology_operation(
            request,
            workspace_id,
            user,
            store,
            ontology_ops.op_restore_ontology_version_draft,
            {
                "ontology_uri": ontology_uri,
                "target_version": body.target_version,
                "summary": body.summary,
            },
            http_method="POST",
            require_editor=True,
        )

    router.add_api_route(
        "/{workspace_id}/ontology/versions/{ontology_uri:path}/restore-draft",
        _ont_29_restore_version_draft,
        methods=["POST"],
        name="_ont_29_restore_version_draft",
    )
