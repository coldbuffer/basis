import pytest

pytest.importorskip("semantica")

from basis.domain.ontology.hub.draft_apply import apply_removals, materialize_restrictions
from basis.domain.ontology.hub.draft_store import save_draft
from basis.domain.ontology.hub.hub_models import DraftDiff, DraftRequest
from basis.domain.ontology.hub.proposal_lifecycle import publish_proposal
from basis.domain.ontology.hub.proposal_store import approve_proposal
from basis.domain.ontology.hub.hub_models import ProposalResponse


def test_materialize_restrictions_builds_nodes_and_edges() -> None:
    ns = "http://example.org/r"
    nodes, edges = materialize_restrictions(
        f"{ns}#ontology",
        [
            {
                "type": "someValuesFrom",
                "class_uri": f"{ns}/Manager",
                "onProperty": f"{ns}/reportsTo",
                "filler_class": f"{ns}/Person",
            }
        ],
    )
    assert len(nodes) == 1
    assert nodes[0]["type"] == "owl:Restriction"
    assert nodes[0]["properties"]["owl:someValuesFrom"] == f"{ns}/Person"
    assert len(edges) == 3
    assert any(edge["type"] == "rdfs:subClassOf" for edge in edges)


@pytest.mark.parametrize(
    ("payload", "predicate", "filler_edge"),
    [
        (
            {
                "type": "allValuesFrom",
                "class_uri": "http://ex.org/C",
                "onProperty": "http://ex.org/p",
                "filler_class": "http://ex.org/D",
            },
            "owl:allValuesFrom",
            "owl:allValuesFrom",
        ),
        (
            {
                "type": "hasValue",
                "class_uri": "http://ex.org/C",
                "onProperty": "http://ex.org/p",
                "filler_individual": "http://ex.org/ind1",
            },
            "owl:hasValue",
            "owl:hasValue",
        ),
        (
            {
                "type": "maxCardinality",
                "class_uri": "http://ex.org/C",
                "onProperty": "http://ex.org/p",
                "cardinality": 2,
            },
            "owl:maxCardinality",
            None,
        ),
        (
            {
                "type": "maxQualifiedCardinality",
                "class_uri": "http://ex.org/C",
                "onProperty": "http://ex.org/p",
                "filler_class": "http://ex.org/D",
                "cardinality": 1,
            },
            "owl:maxQualifiedCardinality",
            "owl:onClass",
        ),
        (
            {
                "property_scope": "data",
                "type": "someValuesFrom",
                "class_uri": "http://ex.org/C",
                "onProperty": "http://ex.org/dp",
                "filler_datatype": "http://www.w3.org/2001/XMLSchema#string",
            },
            "owl:someValuesFrom",
            "owl:someValuesFrom",
        ),
        (
            {
                "property_scope": "data",
                "type": "hasValue",
                "class_uri": "http://ex.org/C",
                "onProperty": "http://ex.org/dp",
                "literal_value": "active",
                "filler_datatype": "http://www.w3.org/2001/XMLSchema#string",
            },
            "owl:hasValue",
            None,
        ),
    ],
)
def test_materialize_restrictions_owl_variants(payload, predicate, filler_edge) -> None:
    nodes, edges = materialize_restrictions("http://ex.org#ontology", [payload])
    assert len(nodes) == 1
    assert predicate in nodes[0]["properties"]
    if filler_edge:
        assert any(edge["type"] == filler_edge for edge in edges)


def test_apply_removals_purges_edge_by_triple_key() -> None:
    from semantica.context import ContextGraph

    graph = ContextGraph()
    graph.add_node("http://ex.org/A", "owl:Class", content="A")
    graph.add_node("http://ex.org/B", "owl:Class", content="B")
    graph.add_edge("http://ex.org/A", "http://ex.org/B", "rdfs:subClassOf")

    class _Session:
        def __init__(self, g: object) -> None:
            self.graph = g

    diff = {"removed_edges": ["http://ex.org/A|rdfs:subClassOf|http://ex.org/B"]}
    _, removed_edges = apply_removals(
        _Session(graph),
        diff,
        diff_list=lambda _d, key: list(diff.get(key) or []),
    )
    assert removed_edges == 1
    assert not graph.find_edges()


def test_apply_removals_purges_nodes_and_edges() -> None:
    from semantica.context import ContextGraph

    graph = ContextGraph()
    graph.add_node("http://ex.org/A", "owl:Class", content="A")
    graph.add_node("http://ex.org/B", "owl:Class", content="B")
    graph.add_edge("http://ex.org/A", "http://ex.org/B", "rdfs:subClassOf")
    edge_id = graph.find_edges()[0]["id"]

    class _Session:
        def __init__(self, g: object) -> None:
            self.graph = g

    diff = {
        "removed_classes": ["http://ex.org/A"],
        "removed_edges": [edge_id],
    }

    removed_nodes, removed_edges = apply_removals(
        _Session(graph),
        diff,
        diff_list=lambda _d, key: list(diff.get(key) or []),
    )
    assert removed_nodes == 1
    assert removed_edges == 1
    assert graph.find_node("http://ex.org/A") is None


def test_publish_applies_restrictions() -> None:
    from semantica.context import ContextGraph

    graph = ContextGraph()
    ns = "http://example.org/rest"
    class_uri = f"{ns}/Team"

    class _Session:
        def __init__(self) -> None:
            self.graph = graph

        def add_nodes(self, nodes):
            for node in nodes:
                graph.add_node(
                    node["id"],
                    node.get("type", "owl:Class"),
                    content=node.get("content"),
                    **(node.get("properties") or {}),
                )
            return len(nodes)

        def add_nodes_and_edges(self, nodes, edges):
            self.add_nodes(nodes)
            for edge in edges:
                graph.add_edge(edge["source"], edge["target"], edge["type"], weight=edge.get("weight", 1.0))
            return len(nodes), len(edges)

    drafts: dict = {}
    proposals: dict = {}
    versions: dict = {}
    body = DraftRequest(
        ontology_uri=f"{ns}#ontology",
        diff=DraftDiff(
            added_classes=[class_uri],
            added_restrictions=[
                {
                    "type": "someValuesFrom",
                    "class_uri": class_uri,
                    "onProperty": f"{ns}/hasMember",
                    "filler_class": f"{ns}/Person",
                }
            ],
        ),
        author="editor@test.io",
        summary="draft",
    )
    saved = save_draft(drafts, body)
    proposal = ProposalResponse(
        proposal_id="prop_rest123456",
        draft_id=saved["draft_id"],
        ontology_uri=f"{ns}#ontology",
        summary="propose",
        author="editor@test.io",
        reviewer=None,
        state="proposed",
        impact_analysis={},
        shacl_validation={},
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        comments=[],
    )
    proposals[proposal.proposal_id] = proposal
    approve_proposal(proposals, proposal.proposal_id)
    result = publish_proposal(_Session(), proposals, drafts, versions, proposal.proposal_id)
    assert result["status"] == "published"
    assert result["edges_added"] >= 3
    assert graph.find_node(class_uri) is not None
