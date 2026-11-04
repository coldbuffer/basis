"""Process-wide connection list used by the vendored registry cache.

Basis opens each catalog source with :func:`create_connector` from the
workspace row. This hook stays empty so ``get_connectors`` falls through to
``CONNECTION_STRINGS`` instead of auto-ontology's catalog database.
"""

from __future__ import annotations

from typing import Any


def list_connections() -> list[dict[str, Any]]:
    return []
