from basis.services.graph.reads.diff import diff_graph_states


def test_diff_graph_states_nodes_and_edges() -> None:
    start = {
        "nodes": [
            {"id": "a", "type": "entity", "properties": {"content": "A"}},
            {"id": "b", "type": "entity", "properties": {"content": "B"}},
        ],
        "edges": [{"source_id": "a", "target_id": "b", "type": "rel"}],
    }
    end = {
        "nodes": [
            {"id": "a", "type": "entity", "properties": {"content": "A2"}},
            {"id": "c", "type": "entity", "properties": {"content": "C"}},
        ],
        "edges": [{"source_id": "a", "target_id": "c", "type": "rel"}],
    }
    diff = diff_graph_states(start, end)
    assert diff["added_nodes"] == ["c"]
    assert diff["removed_nodes"] == ["b"]
    assert diff["modified_nodes"] == [{"id": "a", "change": "properties"}]
    assert len(diff["added_edges"]) == 1
    assert diff["added_edges"][0]["target_id"] == "c"
    assert len(diff["removed_edges"]) == 1
    assert diff["removed_edges"][0]["target_id"] == "b"
