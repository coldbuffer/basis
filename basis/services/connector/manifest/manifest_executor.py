"""Protocol executor blocks → internal adapter retriever/mutation shapes."""

from __future__ import annotations

from typing import Any

from basis.services.connector.manifest.manifest_schema import (
    DynamicSchemaLoaderSpec,
    EntityActionSpec,
    PaginatorSpec,
    RestEntityExecutorSpec,
    RestOperationSpec,
    SqlEntityExecutorSpec,
    StreamMutationSpec,
    StreamSpec,
    SubstreamPartitionSpec,
    WriteOpLiteral,
    RetrieverSpec,
)

LIST_OPERATION = "list"
DISCOVER_OPERATION = "discover"
INVOKE_OPERATION = "invoke"


def rest_operation_to_retriever(op: RestOperationSpec) -> RetrieverSpec:
    incremental = op.incremental
    http_method = op.method if op.method in ("GET", "POST") else "GET"
    return RetrieverSpec(
        adapter="rest_declarative",
        path=op.path,
        http_method=http_method,
        request_params=dict(op.query),
        request_headers=dict(op.headers),
        records_field_path=list(op.records),
        paginator=op.pagination or PaginatorSpec(),
        incremental_cursor_param=incremental.param if incremental else None,
        incremental_cursor_inject=incremental.inject_into if incremental else "query",
        request_body_json=op.body,
    )


def rest_operation_to_mutation(
    op: RestOperationSpec, operation: WriteOpLiteral
) -> StreamMutationSpec:
    body = op.body if op.body is not None else {"patch": "{{patch}}"}
    http_method = op.method
    if http_method not in ("POST", "PUT", "PATCH", "DELETE"):
        http_method = {
            "create": "POST",
            "update": "PATCH",
            "upsert": "PUT",
            "delete": "DELETE",
        }[operation]
    return StreamMutationSpec(
        adapter="rest_declarative",
        operation=operation,
        http_method=http_method,
        path_template=op.path,
        request_params=dict(op.query),
        request_headers=dict(op.headers),
        body_template=body,
    )


def entity_rest_to_stream_spec(
    entity: EntityActionSpec, rest: RestEntityExecutorSpec
) -> StreamSpec:
    ops = rest.operations
    if LIST_OPERATION not in ops:
        raise ValueError(
            f"Entity '{entity.id}' rest.operations must include '{LIST_OPERATION}'"
        )
    mutations: dict[WriteOpLiteral, StreamMutationSpec] = {}
    for key in ("create", "update", "upsert", "delete"):
        op_key: WriteOpLiteral = key
        if op_key in ops:
            mutations[op_key] = rest_operation_to_mutation(ops[op_key], op_key)

    extras = entity.model_extra or {}
    retriever = rest_operation_to_retriever(ops[LIST_OPERATION])
    retriever_updates: dict[str, Any] = {}
    if "x-basis-record-fields-unwrap-path" in extras:
        retriever_updates["record_fields_unwrap_path"] = extras[
            "x-basis-record-fields-unwrap-path"
        ]
    if "x-basis-record-filter-jinja" in extras:
        retriever_updates["record_filter_jinja"] = extras[
            "x-basis-record-filter-jinja"
        ]
    if "x-basis-partition-router" in extras:
        retriever_updates["partition_router"] = SubstreamPartitionSpec.model_validate(
            extras["x-basis-partition-router"]
        )
    if retriever_updates:
        retriever = RetrieverSpec.model_validate(
            {**retriever.model_dump(mode="python"), **retriever_updates}
        )

    dynamic_loader = None
    if "x-basis-dynamic-schema-loader" in extras:
        dynamic_loader = DynamicSchemaLoaderSpec.model_validate(
            extras["x-basis-dynamic-schema-loader"]
        )

    return StreamSpec(
        name=entity.id,
        display_name=entity.display_name,
        description=entity.description,
        primary_key=list(entity.primary_key),
        cursor_field=entity.cursor_field,
        default_label_field=entity.default_label_field,
        fields=list(entity.fields),
        dynamic_schema_loader=dynamic_loader,
        retriever=retriever,
        mutations=mutations,
    )


def entity_sql_to_stream_spec(
    entity: EntityActionSpec, sql: SqlEntityExecutorSpec
) -> StreamSpec:
    ops = sql.operations
    dynamic_loader = None
    if DISCOVER_OPERATION in ops:
        dynamic_loader = DynamicSchemaLoaderSpec.model_validate(ops[DISCOVER_OPERATION])
    mutations: dict[WriteOpLiteral, StreamMutationSpec] = {}
    for key in ("create", "update", "upsert", "delete"):
        op_key: WriteOpLiteral = key
        if op_key in ops:
            mutations[op_key] = StreamMutationSpec(
                adapter="sql_alchemy",
                operation=op_key,
            )
    return StreamSpec(
        name=entity.id,
        display_name=entity.display_name,
        description=entity.description,
        primary_key=list(entity.primary_key),
        cursor_field=entity.cursor_field,
        default_label_field=entity.default_label_field,
        fields=list(entity.fields),
        dynamic_schema_loader=dynamic_loader,
        retriever=RetrieverSpec(adapter="sql_alchemy"),
        mutations=mutations,
    )


def binding_params_to_rest_operation(
    params: dict[str, Any], *, write_op: WriteOpLiteral | None = None
) -> dict[str, Any]:
    from basis.services.connector.manifest.manifest_rest_binding import (
        expand_rest_list_params,
        expand_rest_write_params,
    )

    if write_op is None:
        expanded = expand_rest_list_params(params)
        op: dict[str, Any] = {
            "method": expanded.get("http_method", "GET"),
            "path": expanded["path"],
        }
        if expanded.get("request_params"):
            op["query"] = expanded["request_params"]
        if expanded.get("request_headers"):
            op["headers"] = expanded["request_headers"]
        paginator = expanded.get("paginator")
        if paginator and paginator != {"type": "none"}:
            op["pagination"] = paginator
        inc = expanded.get("incremental_cursor_param")
        if inc:
            op["incremental"] = {
                "param": inc,
                "inject_into": expanded.get("incremental_cursor_inject", "query"),
            }
        records = expanded.get("records_field_path")
        if records:
            op["records"] = records
        return op

    expanded = expand_rest_write_params(write_op, params)
    op = {
        "method": expanded["http_method"],
        "path": expanded["path_template"],
    }
    if expanded.get("request_params"):
        op["query"] = expanded["request_params"]
    if expanded.get("request_headers"):
        op["headers"] = expanded["request_headers"]
    if expanded.get("body_template"):
        op["body"] = expanded["body_template"]
    return op


def stream_to_rest_executor(stream: StreamSpec) -> RestEntityExecutorSpec:
    from basis.services.connector.manifest.manifest_rest_binding import (
        compact_rest_list_params,
        compact_rest_write_params,
    )

    operations: dict[str, RestOperationSpec] = {}
    rparams = stream.retriever.model_dump(mode="python", exclude_none=True)
    rparams.pop("adapter", None)
    list_dict = binding_params_to_rest_operation(
        compact_rest_list_params(rparams), write_op=None
    )
    operations[LIST_OPERATION] = RestOperationSpec.model_validate(list_dict)
    for wop, mutation in stream.mutations.items():
        mparams = mutation.model_dump(mode="python", exclude_none=True)
        mparams.pop("adapter", None)
        mparams.pop("operation", None)
        compact = compact_rest_write_params({**mparams, "operation": mutation.operation})
        op_dict = binding_params_to_rest_operation(compact, write_op=wop)
        operations[wop] = RestOperationSpec.model_validate(op_dict)
    return RestEntityExecutorSpec(operations=operations)


def stream_to_sql_executor(stream: StreamSpec) -> SqlEntityExecutorSpec:
    operations: dict[str, Any] = {LIST_OPERATION: {}}
    if stream.dynamic_schema_loader is not None:
        operations[DISCOVER_OPERATION] = stream.dynamic_schema_loader.model_dump(
            mode="python"
        )
    for wop in stream.mutations:
        operations[wop] = {}
    return SqlEntityExecutorSpec(operations=operations)
