#!/usr/bin/env python3
"""Workspace connector HTTP routes must not call domain orchestration directly."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP_CONNECTORS = ROOT / "basis" / "interface" / "http" / "workspace" / "connectors"

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.[a-zA-Z0-9_.]+)",
    re.MULTILINE,
)

# HTTP may import scope constants only; orchestration stays in application/connectors.
ALLOWED_DOMAIN_CONNECTOR_PREFIXES = (
    "basis.domain.connector.connection_scope",
)

FORBIDDEN_DOMAIN_PREFIXES = (
    "basis.domain.integration",
    "basis.domain.connector.primitive_invoke",
)

FORBIDDEN_DOMAIN_CONNECTOR_ROOT = "basis.domain.connector"


def _is_allowed_connector_domain(target: str) -> bool:
    for prefix in ALLOWED_DOMAIN_CONNECTOR_PREFIXES:
        if target == prefix or target.startswith(prefix + "."):
            return True
    if target == FORBIDDEN_DOMAIN_CONNECTOR_ROOT or target.startswith(
        FORBIDDEN_DOMAIN_CONNECTOR_ROOT + "."
    ):
        return False
    return True


def _collect_hits() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if not HTTP_CONNECTORS.is_dir():
        return hits
    for path in sorted(HTTP_CONNECTORS.rglob("*.py")):
        rel = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        for match in IMPORT_RE.finditer(text):
            target = match.group(1).split()[0].rstrip(",")
            for prefix in FORBIDDEN_DOMAIN_PREFIXES:
                if target == prefix or target.startswith(prefix + "."):
                    hits.append((rel, target))
                    break
            if not _is_allowed_connector_domain(target):
                if target == FORBIDDEN_DOMAIN_CONNECTOR_ROOT or target.startswith(
                    FORBIDDEN_DOMAIN_CONNECTOR_ROOT + "."
                ):
                    hits.append((rel, target))
    return hits


def main() -> int:
    hits = _collect_hits()
    if hits:
        print(
            "Connector HTTP must use basis.application.connectors (not domain orchestration):",
            file=sys.stderr,
        )
        for rel, target in sorted(set(hits)):
            print(f"  {rel} -> {target}", file=sys.stderr)
        return 1
    print("OK: workspace connector HTTP imports stay on application use cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
