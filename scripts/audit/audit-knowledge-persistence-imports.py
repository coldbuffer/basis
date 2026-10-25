#!/usr/bin/env python3
"""``domain.knowledge.persistence`` is internal; other domains use narrow façades (e.g. ``knowledge.sql``)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (ROOT / "basis", ROOT / "tests")

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.domain\.knowledge\.persistence(?:\.[a-zA-Z0-9_]+)*)",
    re.MULTILINE,
)

ALLOWED_REL = frozenset(
    {
        "basis/domain/knowledge/sql.py",
        "basis/domain/knowledge/persistence/__init__.py",
        "basis/domain/tenancy/admin/persistence/workspaces.py",
    }
)


def _allowed(path: Path) -> bool:
    rel = str(path.relative_to(ROOT))
    if rel in ALLOWED_REL:
        return True
    return rel.startswith("basis/domain/knowledge/")


def main() -> int:
    errors: list[str] = []
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "archive" in path.parts or _allowed(path):
                continue
            text = path.read_text(encoding="utf-8")
            for match in IMPORT_RE.finditer(text):
                rel = path.relative_to(ROOT)
                errors.append(
                    f"{rel}: forbidden {match.group(1)!r} "
                    "(use basis.domain.knowledge.sql or extend allowlist)"
                )
    if errors:
        for line in sorted(set(errors)):
            print(line, file=sys.stderr)
        return 1
    print("OK: knowledge.persistence imports stay inside knowledge (+ admin workspace purge).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
