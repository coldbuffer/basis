#!/usr/bin/env python3
"""Line 1: block legacy Explorer routes imports under basis/ and tests/."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (ROOT / "basis", ROOT / "tests")
PATTERN = re.compile(
    r"^\s*(?:from|import)\s+semantica\.explorer\.routes|"
    r'["\']semantica\.explorer\.routes',
    re.MULTILINE,
)


def _collect() -> list[str]:
    hits: list[str] = []
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if PATTERN.search(text):
                hits.append(str(path.relative_to(ROOT)))
    return hits


def main() -> int:
    found = sorted(set(_collect()))
    if found:
        print("Legacy semantica.explorer.routes imports:", file=sys.stderr)
        for path in found:
            print(f"  {path}", file=sys.stderr)
        return 1
    print("OK: no legacy Explorer routes imports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
