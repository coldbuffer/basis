import pytest

from basis.services.ontology.browse.preview_read import detect_format, preview_ontology
from basis.services.errors import AdminError


def test_detect_format_turtle_prefix() -> None:
    assert detect_format("@prefix ex: <http://ex/> .\nex:s ex:p ex:o .") == "turtle"


def test_preview_requires_url_or_content() -> None:
    with pytest.raises(AdminError) as exc:
        preview_ontology(
            url=None,
            content=None,
            format=None,
            fetch_url_bytes=lambda _u: b"",
            parse_rdf_sync=lambda _c, _f: ([], [], {}),
        )
    assert exc.value.status == 422


def test_preview_from_inline_turtle() -> None:
    ttl = "@prefix ex: <http://example.org/> .\n<http://example.org/> a owl:Ontology .\n"
    out = preview_ontology(
        url=None,
        content=ttl,
        format="turtle",
        fetch_url_bytes=lambda _u: b"",
        parse_rdf_sync=lambda content, fmt: ([], [], {"uri": "http://example.org/", "name": "Ex"}),
    )
    assert out["uri"] == "http://example.org/"
    assert out["name"] == "Ex"
    assert out["format"] == "turtle"
