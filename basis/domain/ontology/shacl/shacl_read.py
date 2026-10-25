"""SHACL generate / list / validate."""

from __future__ import annotations

import asyncio
from typing import Any

from basis.domain.ontology.shacl.shacl_generate import (
    generate_shacl as generate_shacl_sync,
    list_shacl_shapes as list_shacl_shapes_sync,
)
from basis.domain.ontology.shacl.shacl_validate import validate_shacl as validate_shacl_async
from basis.domain.errors import AdminError


async def generate_shacl(
    session: Any,
    registry: dict[str, Any],
    *,
    uri: str,
    quality_tier: str = "strict",
) -> Any:
    return await asyncio.to_thread(
        generate_shacl_sync,
        session,
        registry,
        uri=uri,
        quality_tier=quality_tier,
    )


async def list_shacl_shapes(
    session: Any,
    registry: dict[str, Any],
    *,
    uri: str,
    shacl_turtle_override: str | None = None,
) -> Any:
    if not uri or not str(uri).strip():
        raise AdminError(422, "validation_error", "Query parameter uri is required.")
    return await asyncio.to_thread(
        list_shacl_shapes_sync,
        session,
        registry,
        uri=uri,
        shacl_turtle_override=shacl_turtle_override,
    )


async def validate_shacl(
    session: Any,
    registry: dict[str, Any],
    *,
    uri: str | None,
    shacl_turtle: str,
) -> Any:
    return await validate_shacl_async(
        session,
        registry,
        uri=uri,
        shacl_turtle=shacl_turtle,
    )
