#!/usr/bin/env python3
"""Every workspace ``router = APIRouter`` module must be reachable from ``mount_workspace.py``."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTTP = ROOT / "basis" / "interface" / "http"
WORKSPACE = HTTP / "workspace"
MOUNT = WORKSPACE / "mount_workspace.py"

INCLUDE_ROUTER_RE = re.compile(r"\binclude_router\s*\(\s*(\w+)")


def _router_imports_from_ast(text: str) -> tuple[dict[str, str], list[str]]:
    """Map include_router alias → dotted module; list modules that export ``router`` directly."""
    alias_map: dict[str, str] = {}
    direct: list[str] = []
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module or node.level:
            continue
        mod = node.module
        dotted = mod if mod.startswith("basis.") else f"basis.{mod}"
        for alias in node.names:
            if alias.name != "router":
                continue
            if alias.asname:
                alias_map[alias.asname] = dotted
            else:
                direct.append(dotted)
    return alias_map, direct


def _dotted_to_path(dotted: str) -> Path | None:
    if not dotted.startswith("basis."):
        return None
    parts = dotted.split(".")
    path = ROOT.joinpath(*parts)
    if path.is_file():
        return path
    py = path.with_suffix(".py")
    if py.is_file():
        return py
    init = path / "__init__.py"
    if init.is_file():
        return init
    return None


def _router_modules_in_file(path: Path) -> set[Path]:
    text = path.read_text(encoding="utf-8")
    if "router = APIRouter" not in text and "APIRouter(tags=" not in text:
        return set()
    return {path}


def _follow_mount(path: Path, seen: set[Path]) -> set[Path]:
    if path in seen or not path.is_file():
        return set()
    seen.add(path)
    text = path.read_text(encoding="utf-8")
    mounted = _router_modules_in_file(path)

    alias_to_module, direct_modules = _router_imports_from_ast(text)
    for mod in direct_modules:
        child = _dotted_to_path(mod)
        if child is not None:
            mounted |= _follow_mount(child, seen)

    for match in INCLUDE_ROUTER_RE.finditer(text):
        alias = match.group(1)
        mod = alias_to_module.get(alias)
        if mod:
            child = _dotted_to_path(mod)
            if child is not None:
                mounted |= _follow_mount(child, seen)

    if "register_ontology_hub_routes" in text:
        hub = WORKSPACE / "ontology" / "ontology_hub.py"
        if hub.is_file():
            mounted |= _follow_mount(hub, seen)

    return mounted


def _all_workspace_router_modules() -> set[Path]:
    found: set[Path] = set()
    for path in WORKSPACE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"^router\s*=\s*APIRouter", text, re.MULTILINE):
            found.add(path.resolve())
    return found


def main() -> int:
    if not MOUNT.is_file():
        print("missing mount_workspace.py", file=sys.stderr)
        return 1

    mount_text = MOUNT.read_text(encoding="utf-8")
    alias_map, direct_modules = _router_imports_from_ast(mount_text)
    seeds = [m for m in (*alias_map.values(), *direct_modules)]

    seen: set[Path] = set()
    mounted: set[Path] = set()
    for dotted in seeds:
        p = _dotted_to_path(dotted)
        if p is not None:
            mounted |= _follow_mount(p, seen)

    all_routers = _all_workspace_router_modules()
    # e2e_helpers mounted separately — still a valid router module
    e2e = (WORKSPACE / "e2e_helpers.py").resolve()
    orphans = sorted(
        p
        for p in all_routers
        if p not in mounted and p.name != "mount_workspace.py" and p != e2e
    )

    if orphans:
        for path in orphans:
            print(f"unmounted workspace router module: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    print(f"OK: {len(all_routers)} workspace APIRouter modules are mounted from mount_workspace.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
