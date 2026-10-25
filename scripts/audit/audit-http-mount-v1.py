#!/usr/bin/env python3
"""``mount_v1.py`` must delegate registration to platform/workspace mount helpers only."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOUNT = ROOT / "basis" / "interface" / "http" / "mount_v1.py"
MAX_LINES = 40
ALLOWED_IMPORT_PREFIXES = (
    "from __future__ import annotations",
    "from fastapi import FastAPI",
    "from basis.interface.http.platform.mount_platform import",
    "from basis.interface.http.workspace.mount_workspace import",
)


def main() -> int:
    errors: list[str] = []
    if not MOUNT.is_file():
        errors.append("missing basis/interface/http/mount_v1.py")
    else:
        lines = MOUNT.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_LINES:
            errors.append(f"{MOUNT.relative_to(ROOT)}: exceeds {MAX_LINES} lines")
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith(("from ", "import ")):
                continue
            if not any(stripped.startswith(prefix) for prefix in ALLOWED_IMPORT_PREFIXES):
                errors.append(
                    f"{MOUNT.relative_to(ROOT)}: unexpected import {stripped!r}"
                )
        if re.search(r"include_router\s*\(", MOUNT.read_text(encoding="utf-8")):
            errors.append(
                f"{MOUNT.relative_to(ROOT)}: must not call include_router directly"
            )
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK: mount_v1.py delegates to platform/workspace mount modules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
