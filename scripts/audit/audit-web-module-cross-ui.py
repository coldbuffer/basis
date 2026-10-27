#!/usr/bin/env python3
"""Forbid cross-module UI imports under ``web/src/modules/`` (P4 guard).

Rules:
- Files under ``web/src/modules/<segment>/`` may import ``@/modules/<segment>/components/…`` only.
- Cross-segment ``…/components/…`` imports are errors unless listed in ``ALLOWED_CROSS_UI``.
- Re-export shims from ``app/shared/workspace`` back under ``modules/*/components`` are forbidden.

Other modules' ``lib/`` imports are allowed (see ``web/src/modules/README.md``).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "web" / "src" / "modules"

IMPORT_RE = re.compile(
    r"""@/modules/(?P<target>[a-z0-9-]+)/components/[^'"]+""",
)

# (importer_segment, imported_segment) — prefer ``app/shared/workspace``; keep empty when possible.
ALLOWED_CROSS_UI: frozenset[tuple[str, str]] = frozenset()

SHIM_MARKERS = (
    "@deprecated Import from `@/components/app/shared/workspace",
    "export {",
)


def module_segment(path: Path) -> str | None:
    try:
        rel = path.relative_to(MODULES)
    except ValueError:
        return None
    parts = rel.parts
    if not parts:
        return None
    return parts[0]


def scan_cross_ui() -> list[str]:
    errors: list[str] = []
    for path in sorted(MODULES.rglob("*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        owner = module_segment(path)
        if not owner:
            continue
        text = path.read_text(encoding="utf-8")
        for match in IMPORT_RE.finditer(text):
            target = match.group("target")
            if target == owner:
                continue
            if (owner, target) in ALLOWED_CROSS_UI:
                continue
            rel = path.relative_to(ROOT)
            errors.append(
                f"{rel}: cross-module UI import @{target}/components "
                f"(owner {owner}); use app/shared/workspace or add a shrinking allowlist entry"
            )
    return errors


def scan_shared_shims() -> list[str]:
    errors: list[str] = []
    for path in sorted(MODULES.rglob("*")):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if "/components/" not in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8")
        if SHIM_MARKERS[0] in text and SHIM_MARKERS[1] in text:
            if "@/components/app/shared/workspace" in text:
                errors.append(
                    f"{path.relative_to(ROOT)}: remove deprecated shared re-export shim"
                )
    return errors


def main() -> int:
    errors = scan_cross_ui() + scan_shared_shims()
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print("OK: web module cross-UI imports within policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
