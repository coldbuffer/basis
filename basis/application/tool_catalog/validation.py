"""Validate named tool arguments and responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from basis.application.connectors.schemas import TOOL_INPUT_MODELS as CONNECTOR_INPUT
from basis.application.connectors.schemas import TOOL_RESPONSE_MODELS as CONNECTOR_RESPONSE
from basis.application.graph.schemas import TOOL_INPUT_MODELS as GRAPH_INPUT
from basis.application.graph.schemas import TOOL_RESPONSE_MODELS as GRAPH_RESPONSE
from basis.application.knowledge.schemas import TOOL_INPUT_MODELS as KNOWLEDGE_INPUT
from basis.application.ontology.schemas import TOOL_INPUT_MODELS as ONTOLOGY_INPUT
from basis.application.knowledge.schemas import TOOL_RESPONSE_MODELS as KNOWLEDGE_RESPONSE
from basis.application.reasoning.schemas import TOOL_INPUT_MODELS as REASONING_INPUT
from basis.application.reasoning.schemas import TOOL_RESPONSE_MODELS as REASONING_RESPONSE
from basis.application.review.schemas import TOOL_INPUT_MODELS as REVIEW_INPUT
from basis.application.review.schemas import TOOL_RESPONSE_MODELS as REVIEW_RESPONSE
from basis.application.workspace.schemas import TOOL_INPUT_MODELS as WORKSPACE_INPUT
from basis.application.workspace.schemas import TOOL_RESPONSE_MODELS as WORKSPACE_RESPONSE
from basis.application.semantica_compat.schemas import TOOL_INPUT_MODELS as SEMANTICA_INPUT
from basis.application.semantica_compat.schemas import TOOL_RESPONSE_MODELS as SEMANTICA_RESPONSE

OPERATION_INPUT_MODELS: dict[str, type[BaseModel]] = {
    **WORKSPACE_INPUT,
    **KNOWLEDGE_INPUT,
    **ONTOLOGY_INPUT,
    **GRAPH_INPUT,
    **REASONING_INPUT,
    **REVIEW_INPUT,
    **CONNECTOR_INPUT,
    **SEMANTICA_INPUT,
}

OPERATION_RESPONSE_MODELS: dict[str, type[BaseModel]] = {
    **WORKSPACE_RESPONSE,
    **KNOWLEDGE_RESPONSE,
    **GRAPH_RESPONSE,
    **REASONING_RESPONSE,
    **REVIEW_RESPONSE,
    **CONNECTOR_RESPONSE,
    **SEMANTICA_RESPONSE,
}


def validation_error_payload(exc: ValidationError) -> dict[str, Any]:
    first = exc.errors()[0] if exc.errors() else {}
    loc = first.get("loc", ())
    field = str(loc[0]) if loc else "arguments"
    return {"error": f"invalid {field}: {first.get('msg', 'validation failed')}"}


def coerce_operation_args(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize args; raises ValidationError on failure."""
    model_cls = OPERATION_INPUT_MODELS.get(name)
    raw = arguments or {}
    if model_cls is None:
        return raw
    if name in {"get_graph_summary", "get_graph_analytics"} and not raw:
        return {}
    validated = model_cls.model_validate(raw)
    return validated.model_dump(exclude_none=True)


def validate_operation_response(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Best-effort response shape check (extra fields allowed)."""
    model_cls = OPERATION_RESPONSE_MODELS.get(name)
    if model_cls is None:
        return payload
    try:
        return model_cls.model_validate(payload).model_dump()
    except ValidationError:
        return payload
