"""REST executor operations compile tests."""

from __future__ import annotations

from basis.services.connector.manifest.manifest_schema import (
    EntityActionSpec,
    RestEntityExecutorSpec,
    RestIncrementalSpec,
    RestOperationSpec,
    entity_to_stream_spec,
)


def test_rest_operations_single_map_compiles_list_and_mutate() -> None:
    entity = EntityActionSpec(
        id="issues",
        display_name="Issues",
        rest=RestEntityExecutorSpec(
            operations={
                "list": RestOperationSpec(
                    method="GET",
                    path="/repos/{{config.owner}}/{{config.repo}}/issues",
                    query={"state": "all"},
                    incremental=RestIncrementalSpec(param="since"),
                ),
                "create": RestOperationSpec(
                    method="POST",
                    path="/repos/{{config.owner}}/{{config.repo}}/issues",
                    body={"patch": "{{patch}}"},
                ),
            }
        ),
    )
    stream = entity_to_stream_spec(entity)
    assert stream.retriever.path.endswith("/issues")
    assert stream.retriever.request_params == {"state": "all"}
    assert stream.retriever.incremental_cursor_param == "since"
    assert "create" in stream.mutations
    assert stream.mutations["create"].http_method == "POST"
