"""SQL engines vendored from NVIDIA auto-ontology (Apache-2.0).

Import a concrete engine only through :func:`create_connector`. Importing this
package does not load warehouse drivers.
"""

from __future__ import annotations

from basis.services.sql_catalog.engines.registry import create_connector

__all__ = ["create_connector"]
