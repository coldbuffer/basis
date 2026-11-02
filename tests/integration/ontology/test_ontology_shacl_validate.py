import asyncio

import pytest

pytest.importorskip("semantica")

from basis.services.ontology.shacl.shacl_validate import validate_shacl
from basis.services.errors import AdminError


def test_validate_empty_turtle_raises() -> None:
    class _Session:
        graph = object()

    async def _run() -> None:
        with pytest.raises(AdminError) as exc:
            await validate_shacl(_Session(), {}, uri="http://ex.org/o", shacl_turtle="  ")
        assert exc.value.status == 422

    asyncio.run(_run())


def test_validate_without_uri_returns_unavailable() -> None:
    class _Session:
        graph = object()

    async def _run() -> None:
        result = await validate_shacl(
            _Session(),
            {},
            uri=None,
            shacl_turtle="@prefix sh: <http://www.w3.org/ns/shacl#> .\n",
        )
        assert result["status"] == "unavailable"
        assert "No target ontology URI" in result["message"]

    asyncio.run(_run())
