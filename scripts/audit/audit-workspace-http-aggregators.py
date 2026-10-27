#!/usr/bin/env python3
"""Workspace HTTP route aggregators must not define handlers (only include_router / hub register)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP = ROOT / "basis" / "interface" / "http"

AGGREGATORS = (
    "workspace/connectors/__init__.py",
    "workspace/documents/__init__.py",
    "workspace/graph/__init__.py",
    "workspace/graph/graph_session_routes.py",
    "workspace/ledger/__init__.py",
    "workspace/sources/__init__.py",
    "workspace/ontology/__init__.py",
    "workspace/review/__init__.py",
    "workspace/review/resolve.py",
)

ROUTE_DECORATOR_RE = re.compile(
    r"^\s*@router\.(get|post|put|patch|delete|head|options|api_route)\b",
    re.MULTILINE,
)
MOUNT_RE = re.compile(
    r"\b(include_router|register_ontology_hub_routes)\s*\(",
)


def main() -> int:
    errors: list[str] = []
    for name in AGGREGATORS:
        path = HTTP / name
        if not path.is_file():
            errors.append(f"missing aggregator: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        if ROUTE_DECORATOR_RE.search(text):
            errors.append(
                f"{path.relative_to(ROOT)}: aggregators must not use @router.* "
                "(move handlers to dedicated route modules)"
            )
        if not MOUNT_RE.search(text):
            errors.append(
                f"{path.relative_to(ROOT)}: expected include_router or "
                "register_ontology_hub_routes"
            )
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print(f"OK: {len(AGGREGATORS)} workspace HTTP aggregators are thin mount modules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
