"""P0 provider synthesis: merge_service and batch build."""

from __future__ import annotations

import json

from basis.services.connector.adapters.rest.providers.github import github_manifest
from basis.services.connector.manifest.manifest_schema import ConnectorManifest
from basis.services.connector.manifest.provider_bundle import manifest_wire_payload
from basis.services.connector.synthesis.batches import load_batch
from basis.services.connector.synthesis.merge import merge_service


def _canonical_manifest(m: ConnectorManifest) -> dict:
    """Compare manifests without ship-tier or key order noise."""
    payload = manifest_wire_payload(m)
    payload.pop("x-basis-ship-tier", None)
    return payload


def test_merge_github_matches_generator() -> None:
    expected = github_manifest()
    merged = merge_service(
        "github",
        prefer_anyconnect_procedures=False,
        overlay_registry_auth=False,
    )
    assert _canonical_manifest(merged) == _canonical_manifest(expected)


def test_batch_0_and_1_definitions() -> None:
    b0 = load_batch(0)
    assert b0.services == ["postgres", "mysql", "github"]
    assert b0.ship_tier_default == "ga"
    b1 = load_batch(1)
    assert b1.services == ["slack", "notion"]
    assert b1.ship_tier_default == "beta"
    b2 = load_batch(2)
    assert b2.services == ["gitlab", "jira"]
    assert b2.catalog_procedures_only == frozenset()
    b3 = load_batch(3)
    assert b3.services == ["hubspot"]
    b4 = load_batch(4)
    assert len(b4.services) == 9
    assert b4.ship_tier_default == "catalog"
    assert b4.prefer_anyconnect_procedures is False


def test_merge_hubspot_entity_streams() -> None:
    m = merge_service("hubspot", ship_tier="beta", overlay_registry_auth=False)
    names = {a.id for a in m.entity_actions()}
    assert names == {"companies", "contacts", "deals"}
    assert m.auth


def test_merge_notion_entity_and_dynamic_loader() -> None:
    m = merge_service("notion", ship_tier="beta", prefer_anyconnect_procedures=False)
    assert m.service == "notion"
    assert len(m.entity_actions()) == 1
    assert m.entity_actions()[0].id == "database_pages"
    extra = m.entity_actions()[0].model_extra or {}
    assert extra.get("x-basis-dynamic-schema-loader") is not None


def test_executor_index_gitlab_jira_paths() -> None:
    from basis.services.connector.synthesis.executor_index import invoke_wire_for_action

    gl = invoke_wire_for_action("gitlab", "gitlab.list_projects")
    assert gl == {"method": "GET", "path": "/api/v4/projects"}
    jr = invoke_wire_for_action("jira", "jira.search_issues")
    assert jr is not None
    assert "cloudId" in jr["path"]

