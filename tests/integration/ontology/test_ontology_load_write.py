import pytest

from basis.services.ontology.hub.registry_write import load_ontology
from basis.services.errors import AdminError


def test_load_ontology_requires_payload() -> None:
    class _Session:
        pass

    with pytest.raises(AdminError) as exc:
        load_ontology(
            _Session(),
            {},
            url=None,
            content=None,
            format=None,
            fetch_url_bytes=lambda _u: b"",
            parse_rdf_sync=lambda _c, _f: ([], [], {}),
            content_likely_owl=lambda _s: False,
            convert_ontology_to_graph=lambda _d: ([], []),
        )
    assert exc.value.status == 422
