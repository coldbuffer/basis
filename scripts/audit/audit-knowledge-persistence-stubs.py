#!/usr/bin/env python3
"""Knowledge SQL layout: implementations under persistence/; only sql.py at package root."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "basis" / "domain" / "knowledge"
ALLOWED_ROOT_SQL = frozenset({"sql.py"})
SCAN_DIRS = (ROOT / "basis", ROOT / "tests")
LEGACY_SQL_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.domain\.knowledge\.sql_[a-z0-9_]+)",
    re.MULTILINE,
)


def main() -> int:
    errors: list[str] = []
    for path in sorted(KNOWLEDGE.glob("sql*.py")):
        if path.name not in ALLOWED_ROOT_SQL:
            errors.append(
                f"{path.relative_to(ROOT)}: remove root SQL module; use persistence/{path.name}"
            )
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "archive" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for match in LEGACY_SQL_IMPORT_RE.finditer(text):
                rel = path.relative_to(ROOT)
                errors.append(f"{rel}: use persistence package, not {match.group(1)}")
    if errors:
        for line in sorted(set(errors)):
            print(line, file=sys.stderr)
        return 1
    print("OK: knowledge SQL modules only under persistence/ (+ sql.py façade).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
