from basis.services.graph.temporal.read import get_temporal_bounds, get_temporal_snapshot


def test_get_temporal_bounds_from_session() -> None:
    class _Session:
        def get_temporal_bounds(self) -> dict[str, str]:
            return {"min": "2020-01-01T00:00:00", "max": "2021-01-01T00:00:00"}

    assert get_temporal_bounds(_Session()) == {
        "min": "2020-01-01T00:00:00",
        "max": "2021-01-01T00:00:00",
    }


def test_get_temporal_snapshot_from_session() -> None:
    class _Session:
        def get_active_nodes(self, *, at_time):  # noqa: ANN001
            return [{"id": "n1"}, {"id": "n2"}]

    out = get_temporal_snapshot(_Session(), "2024-06-01")
    assert out["active_node_count"] == 2
    assert out["active_node_ids"] == ["n1", "n2"]
    assert out["timestamp"].startswith("2024-06-01")
