#!/usr/bin/env python3
"""Report MCP ``OPERATIONS`` tools vs ``op_*`` references under workspace HTTP (P1.5 parity)."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "basis" / "application" / "tool_catalog" / "catalog.py"
HTTP_WORKSPACE = ROOT / "basis" / "interface" / "http" / "workspace"

# Tools with no REST ``op_*`` twin in workspace HTTP (grep heuristic). Keep in sync with
# docs/architecture/http-mcp-parity-gap.md — new OPERATIONS keys must align HTTP or land here.
MCP_ONLY_OK = frozenset(
    {
        # application/semantica_compat — agent graph loop; REST uses domain reads/writes
        "add_entity",
        "add_relationship",
        "export_graph",
        "extract_entities",
        "extract_relations",
        "find_precedents",
        "get_causal_chain",
        "get_graph_analytics",
        "get_graph_summary",
        "query_decisions",
        "query_graph",
        "record_decision",
        "update_node",
        # application/connectors — HTTP uses richer catalog/connection helpers
        "describe_connector_service",
        "list_connector_catalog",
        "list_connector_connections",
        "list_connector_table_mappings",
    }
)

OP_CALL_RE = re.compile(r"\bop_[a-z0-9_]+\b")


def _operations_dict_node(tree: ast.Module) -> ast.Dict | None:
    for node in tree.body:
        value: ast.expr | None = None
        target_id: str | None = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    target_id = target.id
                    value = node.value
                    break
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_id = node.target.id
            value = node.value
        if target_id == "OPERATIONS" and isinstance(value, ast.Dict):
            return value
    return None


def _operation_names_from_catalog() -> list[str]:
    text = CATALOG.read_text(encoding="utf-8")
    tree = ast.parse(text)
    op_dict = _operations_dict_node(tree)
    if op_dict is None:
        raise RuntimeError("OPERATIONS dict not found in catalog.py")
    keys: list[str] = []
    for key in op_dict.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.append(key.value)
    return sorted(keys)


def _workspace_http_text() -> str:
    parts: list[str] = []
    if not HTTP_WORKSPACE.is_dir():
        return ""
    for path in sorted(HTTP_WORKSPACE.rglob("*.py")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _tool_to_op_symbol(tool_name: str) -> str:
    return f"op_{tool_name}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any tool (except MCP_ONLY_OK) has no op_* reference in workspace HTTP",
    )
    args = parser.parse_args()

    if not CATALOG.is_file():
        print(f"missing {CATALOG.relative_to(ROOT)}", file=sys.stderr)
        return 1

    tools = _operation_names_from_catalog()
    http_blob = _workspace_http_text()
    http_ops = set(OP_CALL_RE.findall(http_blob))

    missing: list[str] = []
    for name in tools:
        op = _tool_to_op_symbol(name)
        if op in http_ops or name in MCP_ONLY_OK:
            continue
        missing.append(name)

    print(f"OPERATIONS tools: {len(tools)}")
    print(f"Distinct op_* in workspace HTTP: {len(http_ops)}")
    if missing:
        print("\nNo matching op_* in workspace HTTP (may be MCP-only or gap):")
        for name in missing:
            print(f"  - {name} ({_tool_to_op_symbol(name)})")

    if args.strict and missing:
        not_ok = [n for n in missing if n not in MCP_ONLY_OK]
        if not_ok:
            print(
                f"\nstrict: {len(not_ok)} tool(s) without workspace HTTP op_* reference",
                file=sys.stderr,
            )
            return 1

    if not missing:
        print("OK: every OPERATIONS tool has a workspace HTTP op_* reference or is allowlisted.")
    else:
        print(
            "\n(report-only) Triage gaps in docs/architecture/http-mcp-parity-gap.md before P2."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
