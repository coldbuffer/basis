#!/usr/bin/env python3
"""``mount_platform.py`` must mount every platform HTTP route module."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOUNT = ROOT / "basis" / "interface" / "http" / "platform" / "mount_platform.py"

REQUIRED_PLATFORM_MODULES = frozenset(
    {
        "audit",
        "e2e_helpers",
        "model_providers",
        "models",
        "organizations",
        "platform_info",
        "reasoning",
        "settings",
        "users",
    }
)

PLATFORM_IMPORT_RE = re.compile(
    r"from basis\.interface\.http\.platform\.([a-z0-9_]+) import router\b",
)
PLATFORM_AUTH_IMPORT_RE = re.compile(
    r"from basis\.interface\.http\.platform_auth import router",
)


def main() -> int:
    errors: list[str] = []
    if not MOUNT.is_file():
        errors.append("missing platform/mount_platform.py")
        return 1
    text = MOUNT.read_text(encoding="utf-8")
    imported = {match.group(1) for match in PLATFORM_IMPORT_RE.finditer(text)}
    missing = sorted(REQUIRED_PLATFORM_MODULES - imported)
    extra = sorted(imported - REQUIRED_PLATFORM_MODULES)
    if missing:
        errors.append(f"mount_platform.py missing platform imports: {', '.join(missing)}")
    if extra:
        errors.append(f"mount_platform.py unexpected platform imports: {', '.join(extra)}")
    if not PLATFORM_AUTH_IMPORT_RE.search(text):
        errors.append("mount_platform.py must import router from platform_auth")
    if "_PLATFORM_ROUTERS" not in text:
        errors.append("mount_platform.py must define _PLATFORM_ROUTERS")
    if "users_router" not in text or "mount_platform_e2e_helpers" not in text:
        errors.append(
            "mount_platform.py must mount users at api root and expose mount_platform_e2e_helpers"
        )
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK: mount_platform.py imports all platform HTTP route modules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
