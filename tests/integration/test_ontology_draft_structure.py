"""Draft diff structure edges (subClassOf, domain, range)."""

from __future__ import annotations

import pytest

pytest.importorskip("semantica")

from basis.domain.ontology.hub.draft_store import save_draft
from basis.domain.ontology.hub.draft_structure import structure_change_summary, structure_edges_from_diff
from basis.domain.ontology.hub.hub_models import DraftDiff, DraftRequest, ProposalResponse
from basis.domain.ontology.hub.proposal_lifecycle import publish_proposal, submit_proposal
from basis.domain.ontology.hub.proposal_store import approve_proposal
from basis.domain.ontology.hub.hub_models import ProposalRequest


def test_structure_edges_from_modified_classes_and_rdfs_subclass_axiom() -> None:
    child = "urn:trellis:Document"
    parent = "urn:trellis:Class"
    diff = DraftDiff(
        modified_classes={child: {"subClassOf": parent}},
        added_axioms=[{"type": "rdfs:subClassOf", "subject": "urn:trellis:Artifact", "object": parent}],
    )
    edges = structure_edges_from_diff(diff)
    types = {(e["source"], e["type"], e["target"]) for e in edges}
    assert (child, "rdfs:subClassOf", parent) in types
    assert ("urn:trellis:Artifact", "rdfs:subClassOf", parent) in types
    summary = structure_change_summary(diff)
    assert summary["structure_edge_total"] == 2
    assert summary["subclass_edges"] == 2


def test_publish_applies_modified_property_domain_range() -> None:
    drafts: dict = {}
    proposals: dict = {}
    versions: dict = {}
    prop_uri = "urn:trellis:contains"
    domain_uri = "urn:trellis:Document"
    range_uri = "urn:trellis:Artifact"
    ontology_uri = "https://basis.local/ontology/trellis#"
    body = DraftRequest(
        ontology_uri=ontology_uri,
        diff=DraftDiff(
            modified_properties={
                prop_uri: {"domain": domain_uri, "range": range_uri},
            },
        ),
        author="a@test",
        summary="domain range via modified_properties",
    )
    saved = save_draft(drafts, body)
    proposal = ProposalResponse(
        proposal_id="prop_domrange123",
        draft_id=saved["draft_id"],
        ontology_uri=ontology_uri,
        summary="propose",
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
        added_edges: list = []

        def add_nodes(self, nodes):
            return len(nodes)

        def add_nodes_and_edges(self, nodes, edges):
            self.added_edges.extend(edges)
            return len(nodes), len(edges)

    session = _Session()
    approve_proposal(proposals, proposal.proposal_id)
    result = publish_proposal(session, proposals, drafts, versions, proposal.proposal_id)
    assert result["edges_added"] == 2
    edge_types = {(e["source"], e["type"], e["target"]) for e in session.added_edges}
    assert (prop_uri, "rdfs:domain", domain_uri) in edge_types
    assert (prop_uri, "rdfs:range", range_uri) in edge_types


def test_submit_proposal_impact_includes_structure_counts() -> None:
    drafts: dict = {}
    proposals: dict = {}
    ontology_uri = "https://basis.local/ontology/trellis#"
    body = DraftRequest(
        ontology_uri=ontology_uri,
        diff=DraftDiff(
            added_axioms=[
                {"type": "subClassOf", "subject": "urn:trellis:A", "object": "urn:trellis:B"},
            ],
        ),
        author="a@test",
        summary="axiom only",
    )
    saved = save_draft(drafts, body)

    class _Session:
        graph = type("G", (), {"store": None})()

        def get_nodes(self, skip=0, limit=999_999):
            return [], 0

    submit_proposal(
        _Session(),
        drafts,
        proposals,
        ProposalRequest(draft_id=saved["draft_id"], ontology_uri=ontology_uri, summary="go"),
    )
    proposal = next(iter(proposals.values()))
    impact = proposal.impact_analysis if hasattr(proposal, "impact_analysis") else proposal["impact_analysis"]
    assert impact["class_adds"] == 0
    assert impact["structure_edge_total"] == 1
    assert impact["subclass_edges"] == 1
