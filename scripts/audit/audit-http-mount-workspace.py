#!/usr/bin/env python3
"""``mount_workspace.py`` must mount every root workspace HTTP aggregator."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOUNT = ROOT / "basis" / "interface" / "http" / "workspace" / "mount_workspace.py"

# Root aggregators under ``interface/http/*.py`` (thin mounts or re-exports).
REQUIRED_HTTP_MODULES = frozenset(
    {
        "connectors",
        "documents",
        "graph",
        "ledger",
        "ontology",
        "review",
        "sources",
        "resources",
        "tokens",
    }
)

IMPORT_RE = re.compile(
    r"from basis\.interface\.http\.([a-z_]+) import router",
)


def main() -> int:
    errors: list[str] = []
    if not MOUNT.is_file():
        errors.append("missing workspace/mount_workspace.py")
        return 1
    text = MOUNT.read_text(encoding="utf-8")
    imported = {match.group(1) for match in IMPORT_RE.finditer(text)}
    missing = sorted(REQUIRED_HTTP_MODULES - imported)
    extra = sorted(imported - REQUIRED_HTTP_MODULES)
    if missing:
        errors.append(f"mount_workspace.py missing root imports: {', '.join(missing)}")
    if extra:
        errors.append(f"mount_workspace.py unexpected root imports: {', '.join(extra)}")
    if "_WORKSPACE_ROUTERS" not in text:
        errors.append("mount_workspace.py must define _WORKSPACE_ROUTERS")
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK: mount_workspace.py imports all root workspace HTTP aggregators.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
