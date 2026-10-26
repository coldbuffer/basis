"""SHACL pre-validation for ontology proposals (no Semantica engine store required)."""

from __future__ import annotations

import asyncio
from typing import Any

from basis.domain.ontology.shacl.shacl_generate import generated_shacl_for_uri
from basis.domain.ontology.shacl.shacl_validate import validate_shacl


def _map_shacl_result(result: dict[str, Any]) -> dict[str, Any]:
    status = str(result.get("status") or "unknown")
    if status == "ok":
        return {
            "status": "validated",
            "conforms": bool(result.get("conforms", True)),
            "violations": list(result.get("violations") or []),
            "message": result.get("message"),
        }
    if status == "unavailable":
        return {
            "status": "skipped",
            "reason": result.get("message") or "SHACL validation unavailable",
        }
    return {
        "status": "error" if status == "error" else status,
        "conforms": bool(result.get("conforms", False)),
        "violations": list(result.get("violations") or []),
        "error": result.get("message"),
    }


def validate_proposal_shacl(
    session: Any,
    registry: dict[str, Any] | None,
    ontology_uri: str,
) -> dict[str, Any]:
    uri = str(ontology_uri or "").strip()
    if not uri:
        return {"status": "skipped", "reason": "missing_ontology_uri"}
    if not registry:
        return {"status": "skipped", "reason": "missing_registry"}

    try:
        shacl_turtle, _ = generated_shacl_for_uri(session, registry, uri)
    except Exception as exc:
        return {"status": "error", "error": f"SHACL generation failed: {exc}"}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    try:
        if loop is not None and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    asyncio.run,
                    validate_shacl(session, registry, uri=uri, shacl_turtle=shacl_turtle),
                ).result()
        else:
            result = asyncio.run(
                validate_shacl(session, registry, uri=uri, shacl_turtle=shacl_turtle)
            )
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

    return _map_shacl_result(result)
