"""Shipped SQL provider manifests (Postgres, MySQL). Source for ``providers/*/connector.yaml``."""

from __future__ import annotations

from basis.services.connector.manifest.manifest_actions import entity_action_from_stream
from basis.services.connector.manifest.manifest_schema import (
    AuthSpec,
    CheckEndpointSpec,
    ConfigFieldSpec,
    ConnectorManifest,
    DynamicSchemaLoaderSpec,
    ProviderSpecReference,
    RetrieverSpec,
    StreamMutationSpec,
    StreamSpec,
)


def sql_provider_manifests() -> list[ConnectorManifest]:
    """BOCP manifests for relational databases (`spec.protocol: sql`)."""
    common_dsn_fields = [
        ConfigFieldSpec(
            key="host",
            label="Host",
            input_type="text",
            required=True,
            placeholder="localhost",
        ),
        ConfigFieldSpec(
            key="port",
            label="Port",
            input_type="number",
            required=True,
            default=5432,
        ),
        ConfigFieldSpec(
            key="database",
            label="Database",
            input_type="text",
            required=True,
            placeholder="erp_prod",
        ),
        ConfigFieldSpec(
            key="schema",
            label="Default Schema",
            input_type="text",
            required=False,
            default="public",
        ),
    ]
    common_credentials = [
        ConfigFieldSpec(
            key="username",
            label="Username",
            input_type="text",
            required=True,
        ),
        ConfigFieldSpec(
            key="password",
            label="Password",
            input_type="password",
            required=True,
            secret=True,
        ),
    ]
    sql_stream = StreamSpec(
        name="table_records",
        display_name="Database Table Records",
        description="Relational table rows introspected and synced via SQLAlchemy 2.0.",
        primary_key=["id"],
        dynamic_schema_loader=DynamicSchemaLoaderSpec(type="sql_inspector"),
        retriever=RetrieverSpec(adapter="sql_alchemy"),
        mutations={
            "update": StreamMutationSpec(operation="update", adapter="sql_alchemy"),
            "create": StreamMutationSpec(operation="create", adapter="sql_alchemy"),
        },
    )
    sql_spec = ProviderSpecReference(protocol="sql", openapi=None)

    pg = ConnectorManifest(
        service="postgres",
        display_name="PostgreSQL",
        description="PostgreSQL relational database connector backed by SQLAlchemy 2.0 reflection & parameterized queries.",
        categories=["Database"],
        homepage_url="https://www.postgresql.org",
        spec=sql_spec,
        auth=[
            AuthSpec(
                auth_mode="database_dsn",
                connection_config=common_dsn_fields,
                credentials=common_credentials,
                check=CheckEndpointSpec(
                    method="GET",
                    path="SELECT current_user AS id, current_database() AS name",
                    account_id_path="id",
                    display_name_path="name",
                ),
            )
        ],
        actions=[entity_action_from_stream(sql_stream)],
    )

    mysql_dsn_fields = [
        f.model_copy(update={"default": 3306}) if f.key == "port" else f
        for f in common_dsn_fields
        if f.key != "schema"
    ]
    mysql = ConnectorManifest(
        service="mysql",
        display_name="MySQL",
        description="MySQL relational database connector backed by SQLAlchemy 2.0 reflection & parameterized queries.",
        categories=["Database"],
        homepage_url="https://www.mysql.com",
        spec=sql_spec,
        auth=[
            AuthSpec(
                auth_mode="database_dsn",
                connection_config=mysql_dsn_fields,
                credentials=common_credentials,
                check=CheckEndpointSpec(
                    method="GET",
                    path="SELECT CURRENT_USER() AS id, DATABASE() AS name",
                    account_id_path="id",
                    display_name_path="name",
                ),
            )
        ],
        actions=[entity_action_from_stream(sql_stream)],
    )
    return [pg, mysql]
