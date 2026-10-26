import pytest

from basis.domain.ontology.hub.catalog import (
    delete_alignment,
    suggest_alignment_target_uris,
    upsert_alignment,
)
from basis.domain.tenancy.admin.errors import AdminError


def test_upsert_alignment_stores_in_memory() -> None:
    class _Session:
        def get_node(self, _id):  # noqa: ANN001
            return None

    store: dict = {}
    out = upsert_alignment(
        store,
        _Session(),
        source_uri="http://ex.org/a",
        target_uri="http://ex.org/b",
        relation="skos:exactMatch",
    )
    assert out["id"] in store
    assert store[out["id"]]["source_label"]


def test_suggest_alignment_target_uris_matches_label() -> None:
    store = {
        "a1": {
            "id": "a1",
            "source_uri": "http://ex.org/Person",
            "source_label": "人",
            "target_uri": "https://schema.org/Person",
            "target_label": "Person",
            "relation": "skos:exactMatch",
            "confidence": 0.9,
        }
    }
    hits = suggest_alignment_target_uris(store, label="人", entity_type="class")
    assert {row["uri"] for row in hits} == {"http://ex.org/Person"}


def test_delete_alignment_missing() -> None:
    with pytest.raises(AdminError) as exc:
        delete_alignment({}, "missing")
    assert exc.value.status == 404
