#!/usr/bin/env python3
"""Enforce test file naming conventions (see tests/README.md)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INTEGRATION = re.compile(r"^test_[a-z][a-z0-9]*(_[a-z0-9]+)+\.py$")
USE_CASE = re.compile(r"^test_uc_[a-z][a-z0-9_]+\.py$")
CONTRACT = re.compile(r"^test_contract_[a-z][a-z0-9_]+\.py$")
VITEST = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.test\.ts$")
E2E = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.e2e\.spec\.ts$")


def _fail(errors: list[str]) -> None:
    for line in errors:
        print(line, file=sys.stderr)
    print(f"\n{len(errors)} test naming violation(s). See tests/README.md.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    errors: list[str] = []

    int_dir = ROOT / "tests" / "integration"
    for path in sorted(int_dir.glob("test_*.py")):
        if not INTEGRATION.match(path.name):
            errors.append(f"integration: {path.relative_to(ROOT)} (expected test_<domain>_<behavior>.py)")

    uc_dir = ROOT / "tests" / "use_cases"
    for path in sorted(uc_dir.glob("test_*.py")):
        if not USE_CASE.match(path.name):
            errors.append(f"use_cases: {path.relative_to(ROOT)} (expected test_uc_<slug>.py)")

    contract_dir = ROOT / "tests" / "contract"
    for path in sorted(contract_dir.glob("test_*.py")):
        if not CONTRACT.match(path.name):
            errors.append(f"contract: {path.relative_to(ROOT)} (expected test_contract_<topic>.py)")

    web_src = ROOT / "web" / "src"
    for path in sorted(web_src.rglob("*.test.ts")):
        if not VITEST.match(path.name):
            errors.append(f"vitest: {path.relative_to(ROOT)} (expected kebab-case *.test.ts)")
        stem = path.name[: -len(".test.ts")]
        if not (path.with_name(f"{stem}.ts").is_file() or path.with_name(f"{stem}.tsx").is_file()):
            errors.append(
                f"vitest: {path.relative_to(ROOT)} (no sibling {stem}.ts or {stem}.tsx)",
            )

    legacy_e2e = ROOT / "web" / "e2e"
    if legacy_e2e.is_dir():
        errors.append(
            f"e2e: remove legacy {legacy_e2e.relative_to(ROOT)}/ (Playwright lives under tests/e2e/)",
        )

    e2e_dir = ROOT / "tests" / "e2e" / "specs"
    for path in sorted(e2e_dir.glob("*.ts")):
        if path.name.endswith(".e2e.spec.ts"):
            if not E2E.match(path.name):
                errors.append(f"e2e: {path.relative_to(ROOT)} (invalid e2e spec name)")
        elif path.name.endswith(".spec.ts"):
            errors.append(
                f"e2e: {path.relative_to(ROOT)} (rename to *.e2e.spec.ts)",
            )

    if errors:
        _fail(errors)
    print("audit-test-naming: OK")


if __name__ == "__main__":
    main()
