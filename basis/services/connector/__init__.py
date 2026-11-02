"""Connector domain (BOCP runtime, manifests, adapters, vault)."""

from basis.services.connector.vault.auth_vault import (
    ConnectorAuthVault,
    ConnectorPolicy,
    StoredConnection,
    decrypt_vault_payload,
    encrypt_vault_payload,
)
from basis.services.connector.registry import (
    ConnectorCatalog,
    get_connector_catalog,
)
from basis.services.connector.manifest.manifest_schema import (
    AuthModeLiteral,
    AuthSpec,
    CheckEndpointSpec,
    ConfigFieldSpec,
    ConnectorManifest,
    DynamicSchemaLoaderSpec,
    OAuth2DialectSpec,
    PaginatorSpec,
    RateLimitQuotaSpec,
    RetrieverSpec,
    StreamFieldSpec,
    StreamMutationSpec,
    StreamSpec,
    SubstreamPartitionSpec,
    ToolAnnotationsSpec,
    ToolSpec,
    TwoStepAuthSpec,
)
from basis.services.connector.adapters.rest import (
    RestBatchResult,
    RestDeclarativeStreamAdapter,
)
from basis.services.connector.runtime import (
    ConnectorRuntime,
    DiscoveredStreamInfo,
    UnifiedReadResult,
)
from basis.services.connector.adapters.sql import (
    DiscoveredTableSchema,
    SqlAlchemyStreamAdapter,
    SqlBatchResult,
)

__all__ = [
    "AuthModeLiteral",
    "AuthSpec",
    "CheckEndpointSpec",
    "ConfigFieldSpec",
    "ConnectorAuthVault",
    "ConnectorCatalog",
    "ConnectorManifest",
    "ConnectorPolicy",
    "ConnectorRuntime",
    "DiscoveredStreamInfo",
    "DiscoveredTableSchema",
    "DynamicSchemaLoaderSpec",
    "OAuth2DialectSpec",
    "PaginatorSpec",
    "RateLimitQuotaSpec",
    "RestBatchResult",
    "RestDeclarativeStreamAdapter",
    "RetrieverSpec",
    "SqlAlchemyStreamAdapter",
    "SqlBatchResult",
    "StoredConnection",
    "StreamFieldSpec",
    "StreamMutationSpec",
    "StreamSpec",
    "SubstreamPartitionSpec",
    "ToolAnnotationsSpec",
    "ToolSpec",
    "TwoStepAuthSpec",
    "UnifiedReadResult",
    "decrypt_vault_payload",
    "encrypt_vault_payload",
    "get_connector_catalog",
]
