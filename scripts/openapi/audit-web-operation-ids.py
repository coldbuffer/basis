#!/usr/bin/env python3
"""S0: map web HTTP call patterns to OpenAPI operationIds; write audit artifact."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB_SRC = REPO / "web" / "src"
OPENAPI = REPO / "openapi" / "basis-v1.json"
OUT_JSON = REPO / "openapi" / "web-openapi-operation-audit.json"
OUT_MD = REPO / "openapi" / "web-openapi-operation-audit.md"

# Helpers → OpenAPI path templates (from web path utilities)
HELPER_PATTERNS: list[tuple[str, str]] = [
    (r"authV1Path\(\s*['\"]([^'\"]+)['\"]", "/api/v1/auth/{segment}"),
    (r"platformV1Path\(\s*['\"]([^'\"]+)['\"]", "/api/v1/{segment}"),
    (r"workspaceApiPath\(\s*[^,]+,\s*['\"]([^'\"]+)['\"]", "/api/v1/workspaces/{workspace_id}/{segment}"),
    (r"workspaceApiRoot\(\s*[^)]+\)", "/api/v1/workspaces/{workspace_id}"),
    (r"kbApiPath\(\s*[^,]+,\s*['\"]([^'\"]+)['\"]", "/api/v1/workspaces/{workspace_id}/{segment}"),
    (r"kbApiRoot\(\s*[^)]+\)", "/api/v1/workspaces/{workspace_id}"),
    (r"platformKbsCollectionPath", "/api/v1/workspaces"),
]

LITERAL_V1 = re.compile(r"""['"`](/api/v1/[^'"`\s]+)['"`]""")


def strip_for_path_scan(text: str) -> str:
    """Remove comments so JSDoc examples are not counted as call sites."""
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    lines: list[str] = []
    for line in text.splitlines():
        lines.append(re.sub(r"//.*$", "", line))
    return "\n".join(lines)


def classify_hit(hit: dict[str, str]) -> dict[str, str]:
    path = hit["path"]
    if "..." in path or "<suffix>" in path or "{subpath}" in path or "/{suffix}" in path:
        return {**hit, "kind": "doc_template"}
    if path.startswith("/api/v1/workspaces/{workspace_id}/") and path.count("{") >= 2:
        return {**hit, "kind": "dynamic"}
    return hit


def load_operations() -> dict[str, dict[str, str]]:
    spec = json.loads(OPENAPI.read_text(encoding="utf-8"))
    by_path: dict[str, dict[str, str]] = {}
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method not in ("get", "post", "put", "patch", "delete") or not isinstance(op, dict):
                continue
            oid = op.get("operationId")
            if oid:
                by_path.setdefault(path, {})[method.upper()] = oid
    return by_path


def normalize_template(path: str) -> str:
    path = path.split("?", 1)[0]
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    path = re.sub(r"\{kbId\}", "{workspace_id}", path)
    path = re.sub(r"\{id\}", "{workspace_id}", path)
    return path


def scan_web(*, include_tests: bool) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for file in sorted(WEB_SRC.rglob("*")):
        if file.suffix not in (".ts", ".tsx", ".mjs"):
            continue
        rel = str(file.relative_to(REPO))
        if not include_tests and (".test." in rel or ".spec." in rel):
            continue
        text = strip_for_path_scan(file.read_text(encoding="utf-8"))
        for m in LITERAL_V1.finditer(text):
            hits.append(
                classify_hit({"file": rel, "kind": "literal", "path": normalize_template(m.group(1))}),
            )
        for regex, template in HELPER_PATTERNS:
            for m in re.finditer(regex, text):
                seg = m.group(1) if m.lastindex else ""
                path = template.replace("{segment}", seg.strip("/"))
                hits.append(classify_hit({"file": rel, "kind": "helper", "path": path}))
    return hits


def match_operation(path_template: str, operations: dict[str, dict[str, str]]) -> str | None:
    candidates = [path_template]
    if "{param}" in path_template:
        candidates.append(path_template.replace("{param}", "{workspace_id}"))
    for cand in candidates:
        for openapi_path, methods in operations.items():
            if _path_match(cand, openapi_path):
                return next(iter(methods.values()))
    return None


def _path_match(template: str, openapi_path: str) -> bool:
    t_parts = template.strip("/").split("/")
    o_parts = openapi_path.strip("/").split("/")
    if len(t_parts) != len(o_parts):
        return False
    for t, o in zip(t_parts, o_parts):
        if t.startswith("{") and o.startswith("{"):
            continue
        if t != o:
            return False
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Fail on unmatched non-template paths")
    parser.add_argument("--include-tests", action="store_true")
    args = parser.parse_args()

    operations = load_operations()
    hits = scan_web(include_tests=args.include_tests)
    rows = []
    unmatched = []
    for hit in hits:
        oid = match_operation(hit["path"], operations)
        row = {**hit, "operationId": oid}
        rows.append(row)
        if oid is None and "{" not in hit["path"]:
            unmatched.append(row)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"entries": rows}, indent=2), encoding="utf-8")

    lines = [
        "# Web call-site ↔ OpenAPI operationId audit",
        "",
        f"Generated by `scripts/openapi/audit-web-operation-ids.py`. Entries: **{len(rows)}**.",
        "",
        "| File | Path pattern | operationId |",
        "| --- | --- | --- |",
    ]
    for row in rows[:200]:
        oid = row["operationId"] or "—"
        lines.append(f"| `{row['file']}` | `{row['path']}` | `{oid}` |")
    if len(rows) > 200:
        lines.append(f"| … | … | ({len(rows) - 200} more in JSON) |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if unmatched and args.strict:
        print("Unmatched static paths:", file=sys.stderr)
        for u in unmatched[:20]:
            print(f"  {u['file']}: {u['path']}", file=sys.stderr)
        return 1
    if unmatched:
        print(f"Note: {len(unmatched)} unmatched (non-strict); see {OUT_JSON}", file=sys.stderr)
    print(f"Wrote {OUT_JSON} and {OUT_MD} ({len(rows)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
