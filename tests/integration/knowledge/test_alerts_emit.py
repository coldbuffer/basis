"""Alert emit helpers."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from unittest.mock import MagicMock, patch

from basis.services.errors import AdminError
from basis.services.graph.governance.decision import (
    admin_error_triggers_governance_alert,
    maybe_emit_governance_tripped_for_admin_error,
    maybe_emit_governance_tripped_on_review_approve,
    should_emit_governance_tripped_on_review_approve,
)
from basis.services.knowledge.services.alerts_emit import (
    emit_governance_proposal_proposed_alert,
    emit_governance_tripped_alert,
)


def test_admin_error_triggers_governance_alert() -> None:
    assert admin_error_triggers_governance_alert("shacl_validation_failed")
    assert admin_error_triggers_governance_alert("IMPACT_GATE_TRIPPED")
    assert not admin_error_triggers_governance_alert("not_found")


def test_should_emit_governance_tripped_on_review_approve() -> None:
    assert should_emit_governance_tripped_on_review_approve("impact_gate_blocked")
    assert not should_emit_governance_tripped_on_review_approve("review_closed")
    assert not should_emit_governance_tripped_on_review_approve("graph_projection_error")


def test_maybe_emit_governance_tripped_for_admin_error_skips_non_gate() -> None:
    request = MagicMock()
    knowledge = MagicMock()
    with patch("basis.services.graph.governance.decision.emit_governance_tripped_for_workspace") as emit:
        maybe_emit_governance_tripped_for_admin_error(
            "kb-1",
            knowledge,
            AdminError(404, "not_found", "missing"),
        )
        emit.assert_not_called()


def test_maybe_emit_governance_tripped_on_review_approve_skips_review_closed() -> None:
    request = MagicMock()
    knowledge = MagicMock()
    with patch("basis.services.graph.governance.decision.emit_governance_tripped_for_workspace") as emit:
        maybe_emit_governance_tripped_on_review_approve(
            "kb-1",
            knowledge,
            code="review_closed",
            message="closed",
        )
        emit.assert_not_called()


def test_emit_governance_tripped(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "gov@example.com", "password": "password1", "display_name": "Gov"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    knowledge = client.app.state.knowledge_store

    emit_governance_tripped_alert(
        knowledge,
        workspace_id,
        message="Impact gate blocked publish",
        detail={"proposal_id": "p-1"},
    )
    alerts = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()["alerts"]
    assert any(a["kind"] == "governance.tripped" for a in alerts)


def test_emit_governance_proposal_proposed(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "prop@example.com", "password": "password1", "display_name": "Prop"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    knowledge = client.app.state.knowledge_store

    emit_governance_proposal_proposed_alert(
        knowledge,
        workspace_id,
        proposal_id="p-99",
        message="Add Drug class",
        detail={"ontology_uri": "http://example.org/ont"},
    )
    alerts = client.get(f"/api/v1/workspaces/{workspace_id}/alerts", headers=headers).json()["alerts"]
    match = next((a for a in alerts if a["kind"] == "governance.proposal_proposed"), None)
    assert match is not None
    assert match["detail"]["proposal_id"] == "p-99"
