#!/usr/bin/env python3
"""Disallow legacy re-export stubs at ``interface/http/*.py`` (use ``shared/`` or ``workspace/``)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP = ROOT / "basis" / "interface" / "http"

# Former compatibility shims — must not return at package root.
FORBIDDEN_ROOT_STUBS = (
    "deps.py",
    "core_context.py",
    "operation_http.py",
    "request_id.py",
    "rest_v1_concurrency.py",
    "upload_bounds.py",
    "http_path.py",
    "legacy_api_gate.py",
    "legacy_deprecation.py",
    "platform_auth.py",
    "users.py",
    "graph.py",
    "ledger.py",
    "ontology.py",
    "documents.py",
    "sources.py",
    "review.py",
    "review_resolve.py",
    "connectors.py",
    "resources.py",
    "tokens.py",
)

ALLOWED_ROOT_MODULES = frozenset(
    {
        "__init__.py",
        "app.py",
        "mount_v1.py",
    }
)


def main() -> int:
    errors: list[str] = []
    for name in FORBIDDEN_ROOT_STUBS:
        path = HTTP / name
        if path.is_file():
            errors.append(
                f"{path.relative_to(ROOT)}: remove stub; import from shared/ or workspace/ instead"
            )
    for path in sorted(HTTP.glob("*.py")):
        if path.name in ALLOWED_ROOT_MODULES:
            continue
        if path.name in FORBIDDEN_ROOT_STUBS:
            continue
        # New root-level modules are allowed if they contain real app wiring (not star re-exports).
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK: no legacy HTTP root re-export stubs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
