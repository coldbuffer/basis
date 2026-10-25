import pytest

pytest.importorskip("semantica")

from basis.domain.ontology.hub.draft_store import save_draft
from basis.domain.ontology.hub.proposal_lifecycle import publish_proposal
from basis.domain.ontology.hub.proposal_store import approve_proposal
from basis.domain.ontology.hub.hub_models import DraftDiff, DraftRequest, ProposalResponse
from basis.domain.tenancy.admin.errors import AdminError


def test_publish_requires_approved_proposal() -> None:
    drafts: dict = {}
    proposals: dict = {}
    versions: dict = {}
    body = DraftRequest(
        ontology_uri="http://example.org/o",
        diff=DraftDiff(added_classes=["http://example.org/o#C"]),
        author="a@test",
        summary="draft",
    )
    saved = save_draft(drafts, body)
    proposal = ProposalResponse(
        proposal_id="prop_test123456",
        draft_id=saved["draft_id"],
        ontology_uri="http://example.org/o",
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

        def add_nodes(self, nodes):
            return len(nodes)

    with pytest.raises(AdminError) as exc:
        publish_proposal(_Session(), proposals, drafts, versions, proposal.proposal_id)
    assert exc.value.status == 400

    approve_proposal(proposals, proposal.proposal_id)
    result = publish_proposal(_Session(), proposals, drafts, versions, proposal.proposal_id)
    assert result["status"] == "published"
    assert result["nodes_added"] == 1
    assert len(versions.get("http://example.org/o", [])) == 1


def test_publish_applies_edges_and_individuals() -> None:
    drafts: dict = {}
    proposals: dict = {}
    versions: dict = {}
    ns = "http://example.org/pub"
    class_uri = f"{ns}/Person"
    prop_uri = f"{ns}/knows"
    ind_uri = f"{ns}/Alice"
    body = DraftRequest(
        ontology_uri=f"{ns}#ontology",
        diff=DraftDiff(
            added_classes=[class_uri],
            added_properties=[prop_uri],
            added_individuals=[ind_uri],
            added_edges=[
                {
                    "source": prop_uri,
                    "target": class_uri,
                    "type": "rdfs:domain",
                }
            ],
            added_axioms=[
                {"type": "subClassOf", "subject": class_uri, "object": f"{ns}/Agent"},
            ],
        ),
        author="a@test",
        summary="draft",
    )
    saved = save_draft(drafts, body)
    proposal = ProposalResponse(
        proposal_id="prop_edges123456",
        draft_id=saved["draft_id"],
        ontology_uri=f"{ns}#ontology",
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
        added_nodes: list = []
        added_edges: list = []

        def add_nodes(self, nodes):
            self.added_nodes.extend(nodes)
            return len(nodes)

        def add_nodes_and_edges(self, nodes, edges):
            self.added_nodes.extend(nodes)
            self.added_edges.extend(edges)
            return len(nodes), len(edges)

    session = _Session()
    approve_proposal(proposals, proposal.proposal_id)
    result = publish_proposal(session, proposals, drafts, versions, proposal.proposal_id)
    assert result["status"] == "published"
    assert result["nodes_added"] == 3
    assert result["edges_added"] == 2
    edge_types = {edge["type"] for edge in session.added_edges}
    assert "rdfs:domain" in edge_types
    assert "rdfs:subClassOf" in edge_types
