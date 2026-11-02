"""Shared limits for workspace graph route modules."""

from __future__ import annotations

import asyncio

from basis.services.graph.sparql.read import _SPARQL_MAX_CONCURRENT

sparql_semaphore = asyncio.Semaphore(_SPARQL_MAX_CONCURRENT)
link_prediction_semaphore = asyncio.Semaphore(2)
