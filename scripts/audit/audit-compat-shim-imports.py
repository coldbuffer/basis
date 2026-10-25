#!/usr/bin/env python3
"""Block reintroduction of removed compatibility re-export modules."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (ROOT / "basis", ROOT / "tests")

# Deleted shims — must not exist on disk.
REMOVED_SHIM_FILES = (
    "basis/platform/admin/migrations.py",
    "basis/platform/admin/postgres_migrations.py",
    "basis/platform/admin/org_backfill.py",
    "basis/transport/http/openapi_v1_export.py",
    "basis/transport/http/openapi_spec.py",
    "basis/transport/http/ingest_tasks.py",
)

# If these paths are imported from ``basis/`` or ``tests/``, CI fails.
FORBIDDEN_IMPORT_PREFIXES = (
    "basis.domain.tenancy.admin.migrations",
    "basis.domain.tenancy.admin.postgres_migrations",
    "basis.domain.tenancy.admin.org_backfill",
    "basis.interface.http.openapi_v1_export",
    "basis.interface.http.openapi_spec",
    "basis.interface.http.ingest_tasks",
)

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.[a-zA-Z0-9_.]+)",
    re.MULTILINE,
)


def _collect_imports() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = str(path.relative_to(ROOT))
            text = path.read_text(encoding="utf-8")
            for match in IMPORT_RE.finditer(text):
                target = match.group(1).split()[0].rstrip(",")
                for prefix in FORBIDDEN_IMPORT_PREFIXES:
                    if target == prefix or target.startswith(prefix + "."):
                        hits.append((rel, prefix))
                        break
    return hits


def main() -> int:
    revived = [rel for rel in REMOVED_SHIM_FILES if (ROOT / rel).is_file()]
    hits = _collect_imports()
    failed = False
    if revived:
        failed = True
        print("Compatibility shim files were reintroduced:", file=sys.stderr)
        for rel in revived:
            print(f"  {rel}", file=sys.stderr)
    if hits:
        failed = True
        print("Imports of removed compatibility modules:", file=sys.stderr)
        for rel, prefix in sorted(set(hits)):
            print(f"  {rel} -> {prefix}", file=sys.stderr)
    if failed:
        return 1
    print(f"OK: {len(REMOVED_SHIM_FILES)} removed shims absent; no forbidden imports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
