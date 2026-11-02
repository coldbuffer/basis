"""SHACL validation concurrency guardrails (Basis-owned)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

_MAX_SHACL_CONCURRENCY = int(os.environ.get("SEMANTICA_MAX_SHACL_CONCURRENCY", "4"))
_shacl_validation_semaphore: tuple[Any, asyncio.Semaphore] | None = None


def get_shacl_semaphore() -> asyncio.Semaphore:
    global _shacl_validation_semaphore
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    if _shacl_validation_semaphore is None or _shacl_validation_semaphore[0] != current_loop:
        _shacl_validation_semaphore = (current_loop, asyncio.Semaphore(_MAX_SHACL_CONCURRENCY))
    return _shacl_validation_semaphore[1]
