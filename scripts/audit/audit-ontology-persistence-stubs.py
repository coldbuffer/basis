#!/usr/bin/env python3
"""Ontology SQL/store layout: implementations must live under ``domain/ontology/persistence/``."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY = ROOT / "basis" / "services" / "ontology"
PERSISTENCE = ONTOLOGY / "persistence"
SCAN_DIRS = (ROOT / "basis", ROOT / "tests")

LEGACY_ONTOLOGY_PERSIST_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.services\.ontology\.(?:hub\.(?:alignment_sql|hub_persistence|draft_store|proposal_store|version_store)|mappings\.sql|reasoning_rules\.sql))\b",
    re.MULTILINE,
)


def main() -> int:
    errors: list[str] = []
    for path in sorted(ONTOLOGY.rglob("*.py")):
        if PERSISTENCE in path.parents:
            continue
        if path.name.startswith("sql") or path.name.endswith(("_sql.py", "_store.py", "_persistence.py")):
            errors.append(
                f"{path.relative_to(ROOT)}: move ontology SQL/store module under domain/ontology/persistence/"
            )
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for match in LEGACY_ONTOLOGY_PERSIST_RE.finditer(text):
                rel = path.relative_to(ROOT)
                errors.append(
                    f"{rel}: use basis.services.ontology.persistence, not {match.group(1)}"
                )
    if errors:
        for line in sorted(set(errors)):
            print(line, file=sys.stderr)
        return 1
    print("OK: ontology SQL and store modules stay under domain/ontology/persistence/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
