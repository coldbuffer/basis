from basis.services.ontology.shacl.shacl_support import (
    basic_shacl_turtle,
    ontology_dict_from_nodes,
    summarize_shacl_shapes,
)


def test_basic_shacl_turtle_includes_node_shape() -> None:
    uri = "http://example.org/o#ontology"
    nodes = [
        {
            "id": "http://example.org/o#Person",
            "type": "owl:Class",
            "content": "Person",
            "properties": {"rdfs:label": "Person"},
        }
    ]
    ttl = basic_shacl_turtle(uri, "Demo", nodes)
    assert "sh:NodeShape" in ttl
    assert "PersonShape" in ttl


def test_ontology_dict_from_nodes_splits_classes_and_properties() -> None:
    uri = "http://example.org/o#ontology"
    nodes = [
        {"id": "http://example.org/o#A", "type": "owl:Class", "properties": {}},
        {"id": "http://example.org/o#p", "type": "owl:ObjectProperty", "properties": {}},
    ]
    edges = [
        {"source": "http://example.org/o#p", "target": "http://example.org/o#A", "type": "rdfs:domain"},
    ]
    data = ontology_dict_from_nodes(uri, "Demo", nodes, edges)
    assert len(data["classes"]) == 1
    assert len(data["properties"]) == 1
    assert data["properties"][0]["domain"] == ["http://example.org/o#A"]


def test_summarize_shapes_counts_node_shapes() -> None:
    ttl = (
        "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
        "ex:Shape1 a sh:NodeShape ; sh:targetClass ex:C1 .\n"
        "ex:Shape2 a sh:NodeShape ; sh:targetClass ex:C2 .\n"
    )
    shapes = summarize_shacl_shapes(ttl)
    assert len(shapes) == 2
