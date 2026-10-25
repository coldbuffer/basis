#!/usr/bin/env python3
"""Disallow deprecated top-level basis package import prefixes in basis/ and tests/."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (ROOT / "basis", ROOT / "tests")

FORBIDDEN_PREFIXES = (
    "basis.transport",
    "basis.integration",
    "basis.platform",
    "basis.ops",
    # Pre-layered layout (v2)
    "basis.api",
    "basis.delivery",
    "basis.interfaces",
    "basis.application.openapi",
    "basis.application.mcp",
    "basis.application.registry",
    "basis.application.operation_registry",
    "basis.interface.contract.mcp.openapi",
    "basis.interface.contract.mcp.annotations",
    "basis.core",
    "basis.control",
    "basis.runtime",
    "basis.tooling",
    "basis.infrastructure",
    "basis.core.kb",
    "basis.core.ingest",
    "basis.core.graph",
    "basis.domain.tenancy.auth",
    "basis.domain.tenancy.models",
    "basis.domain.graph.projection.ontology_legacy",
)

SKIP_FILES = frozenset({"basis/_legacy_imports.py"})

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.[a-zA-Z0-9_.]+)",
    re.MULTILINE,
)


def _is_forbidden(target: str) -> bool:
    for prefix in FORBIDDEN_PREFIXES:
        if target == prefix or target.startswith(prefix + "."):
            return True
    return False


def main() -> int:
    hits: list[tuple[str, str]] = []
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = str(path.relative_to(ROOT))
            if rel in SKIP_FILES:
                continue
            text = path.read_text(encoding="utf-8")
            for match in IMPORT_RE.finditer(text):
                target = match.group(1).split()[0].rstrip(",")
                if _is_forbidden(target):
                    hits.append((rel, target))
    if hits:
        print("Deprecated package import prefixes:", file=sys.stderr)
        for rel, target in sorted(set(hits)):
            print(f"  {rel} -> {target}", file=sys.stderr)
        return 1
    print(f"OK: no forbidden legacy imports ({len(FORBIDDEN_PREFIXES)} prefixes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
