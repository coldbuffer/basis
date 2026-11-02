import pytest

from basis.services.graph.governance.decisions_read import get_causal_chain, list_decisions
from basis.services.errors import AdminError


def test_list_decisions_filters_category() -> None:
    class _Session:
        def get_nodes(self, node_type, skip=0, limit=999_999):  # noqa: ANN001
            return (
                [
                    {
                        "id": "d1",
                        "properties": {"category": "merge", "scenario": "a"},
                    },
                    {
                        "id": "d2",
                        "properties": {"category": "other", "scenario": "b"},
                    },
                ],
                2,
            )

    out = list_decisions(_Session(), category="merge", skip=0, limit=10)
    assert len(out) == 1
    assert out[0]["decision_id"] == "d1"
    assert out[0]["category"] == "merge"


def test_get_causal_chain_missing_raises() -> None:
    class _Session:
        def get_node(self, _id):  # noqa: ANN001
            return None

    with pytest.raises(AdminError) as exc:
        get_causal_chain(_Session(), "missing")
    assert exc.value.status == 404
