"""Ontology hub catalog registration on publish and version backfill."""

from __future__ import annotations

import pytest

pytest.importorskip("semantica")

from basis.domain.ontology.hub.draft_store import save_draft
from basis.domain.ontology.hub.hub_models import DraftDiff, DraftRequest, ProposalResponse
from basis.domain.ontology.hub.proposal_lifecycle import publish_proposal
from basis.domain.ontology.hub.proposal_store import approve_proposal
from basis.domain.ontology.hub.catalog import list_registry
from basis.domain.ontology.hub.registry_ensure import backfill_registry_from_versions


def test_publish_registers_missing_ontology_in_registry() -> None:
    ontology_uri = "http://example.org/reg#ontology"
    drafts: dict = {}
    proposals: dict = {}
    versions: dict = {}
    registry: dict = {}

    body = DraftRequest(
        ontology_uri=ontology_uri,
        diff=DraftDiff(added_classes=[f"{ontology_uri.rstrip('#ontology')}#Person"]),
        author="a@test",
        summary="Registry test ontology",
    )
    saved = save_draft(drafts, body)
    proposal = ProposalResponse(
        proposal_id="prop_registry01",
        draft_id=saved["draft_id"],
        ontology_uri=ontology_uri,
        summary="Publish registers catalog",
        author="a@test",
        reviewer=None,
        state="proposed",
        impact_analysis={},
        shacl_validation={},
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        comments=[],
    )
    proposals[proposal.proposal_id] = proposal

    class _Session:
        graph = type("G", (), {"store": None})()
        added_nodes: list = []

        def get_nodes(self, skip=0, limit=999_999):
            return list(self.added_nodes), 0

        def add_nodes(self, nodes):
            self.added_nodes.extend(nodes)
            return len(nodes)

        def add_nodes_and_edges(self, nodes, edges):
            self.added_nodes.extend(nodes)
            return len(nodes), len(edges or [])

    session = _Session()
    approve_proposal(proposals, proposal.proposal_id)
    result = publish_proposal(
        session,
        proposals,
        drafts,
        versions,
        proposal.proposal_id,
        registry,
    )
    assert result["status"] == "published"
    assert ontology_uri in registry
    assert registry[ontology_uri]["status"] == "active"
    assert result["registry"]["registered"] is True
    assert any(n.get("type") == "owl:Ontology" for n in session.added_nodes)


def test_list_registry_counts_namespace_scoped_entities() -> None:
    ontology_uri = "https://basis.local/ontology/trellis#"
    registry = {
        ontology_uri: {
            "uri": ontology_uri,
            "name": "Trellis",
            "format": "turtle",
            "status": "active",
        }
    }

    class _Session:
        def get_nodes(self, skip=0, limit=999_999):
            return [
                {"id": ontology_uri, "type": "owl:Ontology", "properties": {}},
                {
                    "id": "https://basis.local/ontology/trellis#Person",
                    "type": "owl:Class",
                    "properties": {"rdfs:label": "Person"},
                },
                {
                    "id": "https://basis.local/ontology/trellis#knows",
                    "type": "owl:ObjectProperty",
                    "properties": {"rdfs:label": "knows"},
                },
                {
                    "id": "https://basis.local/ontology/trellis#Alice",
                    "type": "owl:NamedIndividual",
                    "properties": {},
                },
            ], 0

    rows = list_registry(registry, _Session())
    assert len(rows) == 1
    assert rows[0]["class_count"] == 1
    assert rows[0]["property_count"] == 1
    assert rows[0]["concept_count"] == 0


def test_list_registry_counts_editor_urn_entities_via_version_diff() -> None:
    ontology_uri = "https://basis.local/ontology/trellis#"
    registry = {
        ontology_uri: {
            "uri": ontology_uri,
            "name": "Trellis",
            "format": "turtle",
            "status": "active",
        }
    }
    versions = {
        ontology_uri: [
            {
                "version_id": "1.1.0",
                "diff_summary": {
                    "added_classes": ["urn:trellis:Class", "urn:trellis:Document"],
                    "added_properties": ["urn:trellis:contains"],
                },
            }
        ]
    }

    class _Session:
        def get_nodes(self, skip=0, limit=999_999):
            return [
                {"id": "urn:trellis:Class", "type": "owl:Class", "properties": {}},
                {"id": "urn:trellis:Document", "type": "owl:Class", "properties": {}},
                {"id": "urn:trellis:contains", "type": "owl:ObjectProperty", "properties": {}},
            ], 0

    rows = list_registry(registry, _Session(), versions=versions)
    assert rows[0]["class_count"] == 2
    assert rows[0]["property_count"] == 1


def test_backfill_registry_from_versions() -> None:
    uri = "https://basis.local/ontology/trellis#"
    registry: dict = {}
    versions = {
        uri: [
            {
                "version_id": "1.1.0",
                "ontology_uri": uri,
                "state": "published",
                "author": "user@test",
                "date": "2026-10-26T00:00:00+00:00",
                "diff_summary": {},
            }
        ]
    }
    assert backfill_registry_from_versions(registry, versions) == 1
    assert uri in registry
    assert registry[uri]["status"] == "active"
    assert backfill_registry_from_versions(registry, versions) == 0
