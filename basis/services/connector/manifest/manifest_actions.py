"""Build BOCP v2 entity actions from internal stream specs (shipped generators)."""

from __future__ import annotations

from typing import Any

from basis.services.connector.manifest.manifest_executor import (
    INVOKE_OPERATION,
    stream_to_rest_executor,
    stream_to_sql_executor,
)
from basis.services.connector.manifest.manifest_schema import (
    EntityActionSpec,
    MailProcedureExecutorSpec,
    ProcedureActionSpec,
    RestEntityExecutorSpec,
    RestOperationSpec,
    StreamSpec,
    ToolSpec,
)


def entity_action_from_stream(stream: StreamSpec) -> EntityActionSpec:
    if stream.retriever.adapter == "sql_alchemy":
        return EntityActionSpec(
            id=stream.name,
            display_name=stream.display_name,
            description=stream.description,
            primary_key=list(stream.primary_key),
            cursor_field=stream.cursor_field,
            default_label_field=stream.default_label_field,
            fields=list(stream.fields),
            sql=stream_to_sql_executor(stream),
        )
    payload: dict[str, Any] = {
        "id": stream.name,
        "display_name": stream.display_name,
        "description": stream.description,
        "primary_key": list(stream.primary_key),
        "cursor_field": stream.cursor_field,
        "default_label_field": stream.default_label_field,
        "fields": [field.model_dump(mode="python") for field in stream.fields],
        "rest": stream_to_rest_executor(stream).model_dump(mode="python"),
    }
    retriever = stream.retriever
    if stream.dynamic_schema_loader is not None:
        payload["x-basis-dynamic-schema-loader"] = (
            stream.dynamic_schema_loader.model_dump(mode="python")
        )
    if retriever.record_fields_unwrap_path:
        payload["x-basis-record-fields-unwrap-path"] = (
            retriever.record_fields_unwrap_path
        )
    if retriever.record_filter_jinja:
        payload["x-basis-record-filter-jinja"] = retriever.record_filter_jinja
    if retriever.partition_router is not None:
        payload["x-basis-partition-router"] = retriever.partition_router.model_dump(
            mode="python"
        )
    return EntityActionSpec.model_validate(payload)


def procedure_action_from_mail_tool(
    tool: ToolSpec, *, mail_action: str
) -> ProcedureActionSpec:
    short = tool.name or tool.id.split(".")[-1]
    return ProcedureActionSpec(
        id=tool.id,
        name=short,
        display_name=tool.name or short,
        description=tool.description,
        required_scopes=list(tool.required_scopes),
        annotations=tool.annotations,
        input_schema=dict(tool.input_schema),
        output_schema=dict(tool.output_schema),
        mail=MailProcedureExecutorSpec(action=mail_action),
    )


def procedure_action_from_tool(tool: ToolSpec) -> ProcedureActionSpec:
    """Build a BOCP v2 procedure action from an internal tool spec (shipped generators)."""
    short = tool.name or tool.id.split(".")[-1]
    method = tool.http_method or "POST"
    return ProcedureActionSpec(
        id=tool.id,
        name=short,
        display_name=tool.name or short,
        description=tool.description,
        required_scopes=list(tool.required_scopes),
        annotations=tool.annotations,
        input_schema=dict(tool.input_schema),
        output_schema=dict(tool.output_schema),
        rest=RestEntityExecutorSpec(
            operations={
                INVOKE_OPERATION: RestOperationSpec(
                    method=method,
                    path=tool.path_template or "",
                    body_encoding=tool.body_encoding,
                )
            }
        ),
    )
