#!/usr/bin/env python3
"""Disallow new imports of ``basis.domain.graph`` compatibility shims.

Prefer subpackages: ``graph.reads``, ``graph.session.registry``, etc.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH_ROOT = ROOT / "basis" / "domain" / "graph"
SCAN_DIRS = (ROOT / "basis", ROOT / "tests")
ALLOWLIST_PATH = ROOT / "scripts" / "graph-shim-imports.allowlist"

SUBPACKAGES = frozenset(
    {
        "projection",
        "reads",
        "session",
        "governance",
        "temporal",
        "sparql",
        "reasoning",
    }
)

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.domain\.graph\.[a-zA-Z0-9_.]+)",
    re.MULTILINE,
)


def _shim_module_names() -> frozenset[str]:
    names: set[str] = set()
    for path in GRAPH_ROOT.glob("*.py"):
        if path.name == "__init__.py":
            continue
        head = path.read_text(encoding="utf-8")[:300]
        if "Compatibility shim" in head:
            names.add(path.stem)
    return frozenset(names)


def _is_shim_import(target: str) -> bool:
    prefix = "basis.domain.graph."
    if not target.startswith(prefix):
        return False
    rest = target[len(prefix) :]
    first = rest.split(".", 1)[0]
    if first in SUBPACKAGES:
        return False
    shims = _shim_module_names()
    return first in shims


def _collect() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    shims = _shim_module_names()
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(ROOT)
            if rel.parts[:3] == ("basis", "domain", "graph") and len(rel.parts) == 4:
                if path.parent == GRAPH_ROOT and path.stem in shims:
                    continue
            text = path.read_text(encoding="utf-8")
            for match in IMPORT_RE.finditer(text):
                target = match.group(1).split()[0].rstrip(",")
                if _is_shim_import(target):
                    hits.append((str(rel), target))
    return hits


def main() -> int:
    hits = _collect()
    by_file = sorted({path for path, _ in hits})
    allow: set[str] = set()
    if ALLOWLIST_PATH.is_file():
        allow = {
            line.strip()
            for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
    extra = sorted(set(by_file) - allow)
    missing = sorted(allow - set(by_file))
    if extra:
        print("Imports via graph domain compatibility shims (use subpackages):", file=sys.stderr)
        for path in extra:
            targets = sorted({t for p, t in hits if p == path})
            print(f"  {path}", file=sys.stderr)
            for t in targets:
                print(f"    {t}", file=sys.stderr)
    if missing:
        print("Allowlist entries with no shim import (stale):", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
    if extra or missing:
        return 1
    print(
        f"OK: no disallowed graph domain shim imports ({len(shims := _shim_module_names())} shims tracked)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
