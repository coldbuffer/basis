import pytest

from basis.services.errors import AdminError
from basis.services.ontology.hub.registry_write import load_ontology
from basis.services.ontology.io.rdf_io import convert_ontology_to_graph


class _Session:
    def __init__(self) -> None:
        self.nodes: list[dict] = []
        self.edges: list[dict] = []

    def add_nodes_and_edges(self, nodes: list[dict], edges: list[dict]) -> tuple[int, int]:
        self.nodes = nodes
        self.edges = edges
        return len(nodes), len(edges)


def test_load_ontology_requires_payload() -> None:
    with pytest.raises(AdminError) as exc:
        load_ontology(
            _Session(),
            {},
            url=None,
            content=None,
            format=None,
            fetch_url_bytes=lambda _u: b"",
            convert_ontology_to_graph=convert_ontology_to_graph,
        )
    assert exc.value.status == 422


def test_load_ontology_ingests_classes_and_properties() -> None:
    session = _Session()
    registry: dict = {}
    ttl = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://example.org/o> a owl:Ontology ; rdfs:label "O" .
<http://example.org/o#C> a owl:Class ; rdfs:label "C" ;
    rdfs:subClassOf <http://example.org/o#Parent> .
<http://example.org/o#hasName> a owl:DatatypeProperty ; rdfs:label "has name" ;
    rdfs:domain <http://example.org/o#C> .
"""
    result = load_ontology(
        session,
        registry,
        url=None,
        content=ttl,
        format="turtle",
        fetch_url_bytes=lambda _u: b"",
        convert_ontology_to_graph=convert_ontology_to_graph,
    )
    assert result["uri"] == "http://example.org/o"
    assert result["name"] == "O"
    assert {node["id"] for node in session.nodes} == {
        "http://example.org/o",
        "http://example.org/o#C",
        "http://example.org/o#hasName",
    }
    assert registry["http://example.org/o"]["class_count"] == 1
    assert registry["http://example.org/o"]["property_count"] == 1


def test_load_ontology_keeps_import_only_ontology() -> None:
    session = _Session()
    registry: dict = {}
    ttl = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://example.org/all> a owl:Ontology ; rdfs:label "All" ;
    owl:imports <http://example.org/other> .
"""
    result = load_ontology(
        session,
        registry,
        url=None,
        content=ttl,
        format="turtle",
        fetch_url_bytes=lambda _u: b"",
        convert_ontology_to_graph=convert_ontology_to_graph,
    )
    assert result["uri"] == "http://example.org/all"
    assert [node["id"] for node in session.nodes] == ["http://example.org/all"]
    assert session.edges == []


def test_load_ontology_expands_internal_xml_entities() -> None:
    session = _Session()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE rdf:RDF [
  <!ENTITY xsd "http://www.w3.org/2001/XMLSchema#">
  <!ENTITY ex "http://example.org/com/">
]>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
  xmlns:owl="http://www.w3.org/2002/07/owl#">
  <owl:Ontology rdf:about="http://example.org/com/">
    <rdfs:label>Commercial</rdfs:label>
  </owl:Ontology>
  <owl:Class rdf:about="&ex;CommercialLoan">
    <rdfs:label>commercial loan</rdfs:label>
  </owl:Class>
</rdf:RDF>
"""
    load_ontology(
        session,
        {},
        url=None,
        content=xml,
        format="xml",
        fetch_url_bytes=lambda _u: b"",
        convert_ontology_to_graph=convert_ontology_to_graph,
    )
    assert any(node["id"] == "http://example.org/com/CommercialLoan" for node in session.nodes)
