"""REST protocol (`rest_declarative` retriever / mutations / tools)."""

from basis.services.connector.adapters.rest.adapter import (
    RestBatchResult,
    RestDeclarativeStreamAdapter,
)
from basis.services.connector.adapters.rest.curated_dev import curated_rest_manifests

__all__ = [
    "RestBatchResult",
    "RestDeclarativeStreamAdapter",
    "curated_rest_manifests",
]
