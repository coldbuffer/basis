from basis.domain.graph.projection.session import GraphSession
from basis.domain.ontology.hub.alignment_graph import (
    apply_vocabulary_alignment_edge,
    purge_vocabulary_alignment_edges,
    remove_vocabulary_alignment_edge,
)


def test_vocabulary_alignment_edge_round_trip() -> None:
    session = GraphSession()
    alignment = {
        "id": "align-1",
        "source_uri": "http://ex.org/a#Person",
        "target_uri": "https://schema.org/Person",
        "source_label": "人",
        "target_label": "Person",
        "relation": "skos:exactMatch",
        "predicate_uri": "http://www.w3.org/2004/02/skos/core#exactMatch",
        "confidence": 0.9,
    }
    apply_vocabulary_alignment_edge(session, alignment)
    assert len(session.graph.edges) == 1

    assert remove_vocabulary_alignment_edge(session, "align-1") is True
    assert len(session.graph.edges) == 0

    apply_vocabulary_alignment_edge(session, alignment)
    assert purge_vocabulary_alignment_edges(session) == 1
    assert len(session.graph.edges) == 0
