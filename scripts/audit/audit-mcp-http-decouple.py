#!/usr/bin/env python3
"""Keep MCP tool catalog independent of workspace HTTP OpenAPI extensions."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP_ROOT = ROOT / "basis" / "interface" / "http"
SCAN_DIRS = (ROOT / "basis", ROOT / "tests")

REMOVED_FILES = (
    "basis/interface/contract/mcp/annotations.py",
    "basis/interface/contract/mcp/openapi.py",
)

FORBIDDEN_HTTP_SUBSTRINGS = (
    "mcp_tool_openapi",
    "x-basis-mcp-tool",
)

MCP_METADATA_PATH = ROOT / "basis" / "application" / "tool_catalog" / "mcp_metadata.py"

FORBIDDEN_IMPORT_PREFIXES = (
    "basis.interface.contract.mcp.annotations",
    "basis.interface.contract.mcp.openapi",
)

IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+(basis\.[a-zA-Z0-9_.]+)",
    re.MULTILINE,
)


def _http_hits() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if not HTTP_ROOT.is_dir():
        return hits
    for path in sorted(HTTP_ROOT.rglob("*.py")):
        rel = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_HTTP_SUBSTRINGS:
            if needle in text:
                hits.append((rel, needle))
    return hits


def _import_hits() -> list[tuple[str, str]]:
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


def _metadata_input_schema_hits() -> list[str]:
    if not MCP_METADATA_PATH.is_file():
        return []
    text = MCP_METADATA_PATH.read_text(encoding="utf-8")
    if '"input_schema"' in text or "'input_schema'" in text:
        return [str(MCP_METADATA_PATH.relative_to(ROOT))]
    return []


def _catalog_alignment_issues() -> list[str]:
    try:
        from basis.application.tool_catalog.catalog import OPERATIONS
        from basis.application.tool_catalog.mcp_metadata import MCP_TOOL_METADATA
        from basis.application.tool_catalog.validation import OPERATION_INPUT_MODELS
    except Exception as exc:  # noqa: BLE001 — audit surface
        return [f"could not import tool catalog: {exc}"]

    issues: list[str] = []
    catalog = set(OPERATIONS)
    if set(MCP_TOOL_METADATA) != catalog:
        issues.append(
            "MCP_TOOL_METADATA keys != OPERATIONS "
            f"(missing={sorted(catalog - set(MCP_TOOL_METADATA))!r}, "
            f"extra={sorted(set(MCP_TOOL_METADATA) - catalog)!r})"
        )
    if set(OPERATION_INPUT_MODELS) != catalog:
        issues.append(
            "OPERATION_INPUT_MODELS keys != OPERATIONS "
            f"(missing={sorted(catalog - set(OPERATION_INPUT_MODELS))!r}, "
            f"extra={sorted(set(OPERATION_INPUT_MODELS) - catalog)!r})"
        )
    return issues


def main() -> int:
    failed = False
    revived = [rel for rel in REMOVED_FILES if (ROOT / rel).is_file()]
    if revived:
        failed = True
        print("MCP/OpenAPI bridge files were reintroduced:", file=sys.stderr)
        for rel in revived:
            print(f"  {rel}", file=sys.stderr)

    http_hits = _http_hits()
    if http_hits:
        failed = True
        print("Workspace HTTP must not declare MCP tools via OpenAPI:", file=sys.stderr)
        for rel, needle in sorted(set(http_hits)):
            print(f"  {rel}: {needle}", file=sys.stderr)

    import_hits = _import_hits()
    if import_hits:
        failed = True
        print("Imports of removed MCP/OpenAPI bridge modules:", file=sys.stderr)
        for rel, prefix in sorted(set(import_hits)):
            print(f"  {rel} -> {prefix}", file=sys.stderr)

    schema_hits = _metadata_input_schema_hits()
    if schema_hits:
        failed = True
        print(
            "mcp_metadata.py must not define input_schema (use BC schemas.py + tool_catalog.run):",
            file=sys.stderr,
        )
        for rel in schema_hits:
            print(f"  {rel}", file=sys.stderr)

    alignment = _catalog_alignment_issues()
    if alignment:
        failed = True
        print("Static MCP tool catalog alignment:", file=sys.stderr)
        for msg in alignment:
            print(f"  {msg}", file=sys.stderr)

    if failed:
        return 1
    print(
        "OK: MCP list metadata stays in application/tool_catalog; "
        "no HTTP OpenAPI MCP stamps."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
