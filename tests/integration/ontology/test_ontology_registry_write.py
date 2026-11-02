import pytest

from basis.services.ontology.hub.registry_write import remove_ontology, toggle_ontology
from basis.services.errors import AdminError


def test_remove_and_toggle_registry_entry() -> None:
    registry = {
        "http://ex.org#ontology": {"uri": "http://ex.org#ontology", "enabled": True},
    }
    toggled = toggle_ontology(registry, "http://ex.org#ontology")
    assert toggled["enabled"] is False
    assert registry["http://ex.org#ontology"]["enabled"] is False

    removed = remove_ontology(registry, "http://ex.org#ontology")
    assert removed["status"] == "removed"
    assert registry == {}


def test_remove_missing_raises() -> None:
    with pytest.raises(AdminError) as exc:
        remove_ontology({}, "http://missing")
    assert exc.value.status == 404
