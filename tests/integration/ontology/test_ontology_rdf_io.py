import pytest

from basis.services.ontology.io.rdf_io import (
    content_likely_owl_schema,
    convert_ontology_to_graph,
    parse_rdf_sync_for_basis,
)


def test_content_likely_owl_schema_detects_owl() -> None:
    assert content_likely_owl_schema("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n:a a owl:Class .")
    assert not content_likely_owl_schema("@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n:a a skos:Concept .")


def test_parse_rdf_sync_builds_nodes_and_metadata() -> None:
    pytest.importorskip("rdflib")
    ttl = (
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "<http://example.org/o> a owl:Ontology ; rdfs:label \"O\" .\n"
        "<http://example.org/o#C> a owl:Class ; rdfs:label \"C\" .\n"
    )
    nodes, edges, metadata = parse_rdf_sync_for_basis(ttl.encode(), "turtle")
    assert metadata["uri"] == "http://example.org/o"
    assert metadata["name"] == "O"
    assert any(n["id"] == "http://example.org/o#C" for n in nodes)
    assert edges


def test_parse_skos_file_extracts_concepts() -> None:
    pytest.importorskip("rdflib")
    from basis.services.ontology.io.rdf_parse import parse_skos_file

    ttl = (
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
        "<http://example.org/s> a skos:ConceptScheme ; skos:prefLabel \"S\" .\n"
        "<http://example.org/c> a skos:Concept ; skos:prefLabel \"C\" ; skos:inScheme <http://example.org/s> .\n"
    )
    nodes, edges = parse_skos_file(ttl.encode(), "turtle")
    assert {n["type"] for n in nodes} == {"skos:ConceptScheme", "skos:Concept"}
    assert any(e["type"] == "skos:inScheme" for e in edges)


def test_convert_ontology_to_graph_adds_scheme_uri() -> None:
    nodes, edges = convert_ontology_to_graph({
        "uri": "http://example.org/ingest#ontology",
        "name": "Ingest",
        "classes": [{"uri": "http://example.org/ingest#Person", "name": "Person"}],
        "properties": [],
    })
    assert any(n["type"] == "owl:Ontology" for n in nodes)
    class_node = next(n for n in nodes if n["id"] == "http://example.org/ingest#Person")
    assert class_node["properties"]["scheme_uri"] == "http://example.org/ingest#ontology"
