#!/usr/bin/env python3
"""Workspace connector HTTP routes must not call low-level connector runtime/adapters directly."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP_CONNECTORS = ROOT / "basis" / "routes" / "workspace" / "connector"

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.[a-zA-Z0-9_.]+)",
    re.MULTILINE,
)

# Forbidden low-level connector modules inside HTTP routes (routes must use use-case modules).
FORBIDDEN_CONNECTOR_PREFIXES = (
    "basis.domain.integration",
    "basis.services.connector.primitive_invoke",
    "basis.services.connector.runtime",
    "basis.services.connector.adapters",
    "basis.services.connector.manifest",
    "basis.services.connector.synthesis",
    "basis.services.connector.vault.auth_vault",
)


def _collect_hits() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if not HTTP_CONNECTORS.is_dir():
        return hits
    for path in sorted(HTTP_CONNECTORS.rglob("*.py")):
        rel = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        for match in IMPORT_RE.finditer(text):
            target = match.group(1).split()[0].rstrip(",")
            for prefix in FORBIDDEN_CONNECTOR_PREFIXES:
                if target == prefix or target.startswith(prefix + "."):
                    hits.append((rel, target))
                    break
    return hits


def main() -> int:
    hits = _collect_hits()
    if hits:
        print(
            "Connector HTTP must use connector use-case modules (not low-level runtime/adapters):",
            file=sys.stderr,
        )
        for rel, target in sorted(set(hits)):
            print(f"  {rel} -> {target}", file=sys.stderr)
        return 1
    print("OK: workspace connector HTTP imports stay on application use cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
