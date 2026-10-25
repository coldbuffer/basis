#!/usr/bin/env python3
"""One-off: copy OpenAPI snapshot descriptions into route handler docstrings.

Reads `openapi/basis-v1.json` (generate with `scripts/openapi/generate-openapi-v1.py` first).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import json

_REPO = Path(__file__).resolve().parents[2]
_ROUTES_ROOT = _REPO / "basis" / "transport" / "http" / "routes"
_HTTP = _REPO / "basis" / "transport" / "http"
_ONTOLOGY_HUB_FILES = (
    _REPO / "basis" / "interface" / "http" / "ontology_hub_catalog.py",
    _REPO / "basis" / "interface" / "http" / "ontology_hub_governance.py",
)
_OPENAPI = _REPO / "openapi" / "basis-v1.json"
_BACKFILL_PATHS: tuple[Path, ...] = (_ROUTES_ROOT, *_ONTOLOGY_HUB_FILES)


def _load_descriptions_by_function() -> dict[str, str]:
    spec = json.loads(_OPENAPI.read_text(encoding="utf-8"))
    by_func: dict[str, list[tuple[str, str]]] = {}
    for _path, path_item in (spec.get("paths") or {}).items():
        for method, op in path_item.items():
            if method.startswith("x-") or not isinstance(op, dict):
                continue
            oid = str(op.get("operationId") or "")
            desc = str(op.get("description") or "").strip()
            if not oid or not desc:
                continue
            if "_api_v1_" not in oid:
                continue
            func_name = oid.split("_api_v1_", 1)[0]
            by_func.setdefault(func_name, []).append((oid, desc))
    out: dict[str, str] = {}
    for func_name, items in by_func.items():
        if len(items) == 1:
            out[func_name] = items[0][1]
            continue
        # Prefer longest description when duplicates (rare).
        items.sort(key=lambda x: len(x[1]), reverse=True)
        out[func_name] = items[0][1]
        print(f"warn: multiple operationIds for {func_name!r}, using {items[0][0]!r}", file=sys.stderr)
    return out


def _format_docstring(desc: str, indent: str) -> str:
    text = desc.strip().replace("\r\n", "\n")
    if "\n" in text or len(text) > 72:
        inner = text.replace('"""', '\\"\\"\\"')
        return f'{indent}"""\n{inner}\n{indent}"""\n'
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'{indent}"""{escaped}"""\n'


def _should_backfill_handler(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return _is_route_handler(node)


def _is_route_handler(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        fn = dec.func
        if isinstance(fn, ast.Attribute) and fn.attr in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "head",
            "options",
        }:
            if isinstance(fn.value, ast.Name) and fn.value.id == "router":
                return True
    return False


def _set_function_docstring(source: str, node: ast.FunctionDef | ast.AsyncFunctionDef, doc: str) -> str:
    lines = source.splitlines(keepends=True)
    start = node.lineno - 1
    indent = re.match(r"^(\s*)", lines[start]).group(1) + "    "
    new_doc = _format_docstring(doc, indent)

    if not node.body:
        return source

    first = node.body[0]
    existing = ast.get_docstring(node, clean=False)
    if existing is not None and isinstance(first, ast.Expr):
        del_start = first.lineno - 1
        del_end = first.end_lineno or first.lineno
        del lines[del_start:del_end]
        lines.insert(del_start, new_doc)
        return "".join(lines)

    insert_at = first.lineno - 1
    lines.insert(insert_at, new_doc)
    return "".join(lines)


def main() -> None:
    desc_by_func = _load_descriptions_by_function()
    updated_files = 0
    updated_funcs = 0
    missing: list[str] = []

    paths: list[Path] = []
    for root in _BACKFILL_PATHS:
        if root.is_dir():
            paths.extend(sorted(root.rglob("*.py")))
        elif root.is_file():
            paths.append(root)

    for py_path in paths:
        source = py_path.read_text(encoding="utf-8")
        changed = False
        while True:
            tree = ast.parse(source)
            targets = [
                n
                for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and _should_backfill_handler(n)
                and desc_by_func.get(n.name)
                and (ast.get_docstring(n) or "").strip() != desc_by_func[n.name].strip()
            ]
            if not targets:
                break
            node = max(targets, key=lambda n: n.lineno)
            source = _set_function_docstring(source, node, desc_by_func[node.name])
            changed = True
            updated_funcs += 1
        if changed:
            py_path.write_text(source, encoding="utf-8")
            updated_files += 1

    # Report functions in openapi without a matching route name.
    route_funcs = set()
    for root in _BACKFILL_PATHS:
        iter_paths = root.rglob("*.py") if root.is_dir() else [root]
        for py_path in iter_paths:
            tree = ast.parse(py_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    route_funcs.add(node.name)
    for func_name in desc_by_func:
        if func_name not in route_funcs:
            missing.append(func_name)

    print(f"Updated {updated_funcs} handlers in {updated_files} files")
    if missing:
        print(f"warn: {len(missing)} openapi functions not found in route modules", file=sys.stderr)


if __name__ == "__main__":
    main()
