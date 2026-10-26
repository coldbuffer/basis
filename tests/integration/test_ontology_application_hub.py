"""Ontology application hub runner (no HTTP)."""

from __future__ import annotations

from unittest.mock import MagicMock

from basis.application.kernel import WorkspaceCoreContext
from basis.application.ontology.hub_access import run_ontology_hub
from basis.application.ontology.operations import op_list_ontology_registry


def _bare_context(*, ontology_hub=None) -> WorkspaceCoreContext:
    return WorkspaceCoreContext(
        workspace=MagicMock(id="ws_test"),
        user=MagicMock(id="user_test", email="test@example.com"),
        knowledge=MagicMock(),
        store=MagicMock(),
        ontology_hub=ontology_hub,
    )


def test_run_ontology_hub_unavailable_without_runner() -> None:
    ctx = _bare_context(ontology_hub=None)
    payload = run_ontology_hub(ctx, lambda _hub: {"ok": True})
    assert payload["error"] == "ontology_hub_unavailable"


def test_op_list_registry_without_runner_returns_error() -> None:
    ctx = _bare_context(ontology_hub=None)
    payload = op_list_ontology_registry(ctx, {})
    assert payload["error"] == "ontology_hub_unavailable"
