#!/usr/bin/env python3
"""Emit Semantica SDK capability map from installed package APIs + Basis imports.

Output: docs/architecture/semantica-sdk-capability-map.md (local docs tree; /docs/ is gitignored).

Run: uv run python scripts/docs/generate-semantica-sdk-capability-map.py
"""

from __future__ import annotations

import ast
import inspect
import pkgutil
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASIS_PKG = ROOT / "basis"
OUT = ROOT / "docs" / "architecture" / "semantica-sdk-capability-map.md"

ENTITY_METHODS = ["pattern", "regex", "rules", "ml", "huggingface", "llm"]
RELATION_METHODS = [
    "pattern",
    "regex",
    "cooccurrence",
    "similarity",
    "dependency",
    "huggingface",
    "llm",
]
TRIPLET_METHODS = ["pattern", "rules", "huggingface", "llm"]

PRODUCT_CHUNK = frozenset(
    {"recursive", "sentence", "paragraph", "structural", "entity_aware"},
)

_SKIP_DIR_PARTS = frozenset({"__pycache__", ".pytest_cache"})


@dataclass
class ModuleInventory:
    module: str
    source_relpath: str
    all_exports: list[str] | None = None
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)

    def public_names(self) -> list[str]:
        if self.all_exports is not None:
            return list(self.all_exports)
        names = sorted(set(self.classes) | set(self.functions))
        return [n for n in names if not n.startswith("_")]


@dataclass
class BasisSemanticaUsage:
    raw_lines: list[str]
    modules: set[str]
    symbols: set[str]


def _ok(getter, name: str) -> bool:
    try:
        getter(name)
        return True
    except Exception:
        return False


def _parse_basis_semantica_usage() -> BasisSemanticaUsage:
    raw: list[str] = []
    modules: set[str] = set()
    symbols: set[str] = set()
    from_pat = re.compile(
        r"^\s*from\s+(semantica(?:\.[a-zA-Z0-9_]+)*)\s+import\s+(.+)$",
        re.MULTILINE,
    )
    import_pat = re.compile(
        r"^\s*import\s+(semantica(?:\.[a-zA-Z0-9_]*)*(?:\s+as\s+[a-zA-Z0-9_]+)?)\s*$",
        re.MULTILINE,
    )
    for path in sorted(BASIS_PKG.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for m in from_pat.finditer(text):
            mod = m.group(1).strip()
            tail = m.group(2).split("#", 1)[0].strip()
            raw.append(f"{path.relative_to(ROOT)}: from {mod} import {tail}")
            modules.add(mod)
            if tail == "*":
                continue
            for part in tail.split(","):
                name = part.strip().split(" as ", 1)[0].strip()
                if name and name != "(":
                    symbols.add(name)
        for m in import_pat.finditer(text):
            stmt = m.group(1).strip()
            raw.append(f"{path.relative_to(ROOT)}: import {stmt}")
            base = stmt.split(" as ", 1)[0].strip()
            modules.add(base)
    return BasisSemanticaUsage(raw_lines=raw, modules=modules, symbols=symbols)


def _literal_str_list(node: ast.AST) -> list[str] | None:
    if not isinstance(node, ast.List | ast.Tuple):
        return None
    out: list[str] = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
        else:
            return None
    return out


def _inventory_module(py_path: Path, pkg_root: Path) -> ModuleInventory | None:
    rel = py_path.relative_to(pkg_root)
    if any(p in _SKIP_DIR_PARTS for p in rel.parts):
        return None
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        mod_parts = parts[:-1]
    else:
        mod_parts = parts[:-1] + [rel.stem]
    if not mod_parts:
        module = "semantica"
    else:
        module = "semantica." + ".".join(mod_parts)

    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    except SyntaxError:
        return ModuleInventory(module=module, source_relpath=str(rel))

    inv = ModuleInventory(module=module, source_relpath=str(rel))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            inv.classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith(
            "_"
        ):
            inv.functions.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    inv.all_exports = _literal_str_list(node.value)
    inv.classes.sort()
    inv.functions.sort()
    return inv


def _scan_semantica_package(pkg_root: Path) -> list[ModuleInventory]:
    inventories: list[ModuleInventory] = []
    for py_path in sorted(pkg_root.rglob("*.py")):
        if any(p in _SKIP_DIR_PARTS for p in py_path.parts):
            continue
        inv = _inventory_module(py_path, pkg_root)
        if inv is not None:
            inventories.append(inv)
    return inventories


def _basis_hits_symbol(usage: BasisSemanticaUsage, module: str, name: str) -> bool:
    if name in usage.symbols:
        return True
    return False


def _basis_hits_module(usage: BasisSemanticaUsage, module: str) -> bool:
    """True when basis imports this module or a more specific submodule."""
    if module in usage.modules:
        return True
    prefix = module + "."
    return any(m.startswith(prefix) for m in usage.modules)


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |")
    return "\n".join(lines)


def _build_full_catalog(
    inventories: list[ModuleInventory],
    usage: BasisSemanticaUsage,
) -> tuple[str, int, int]:
    """Return (markdown, module_count, symbol_count)."""
    by_top: dict[str, list[ModuleInventory]] = {}
    for inv in inventories:
        rest = inv.module.removeprefix("semantica.").split(".", 1)
        top = rest[0] if rest[0] else "(root)"
        by_top.setdefault(top, []).append(inv)

    total_symbols = 0
    sections: list[str] = []
    sections.append(
        "以下清单由 **AST 扫描** `site-packages/semantica/**/*.py` 得到："
        "各模块的 `__all__`（若为字面量列表）优先；否则为模块顶层 `class` / `def`（不含 `_` 前缀）。"
        "未执行 import，故不包含仅 re-export 且未在 `__all__` 中列出的符号。"
    )
    sections.append("")
    sections.append(
        "**Basis 列**：`是` 表示 `basis/` 的 import 语句中出现该符号名，或 import 了该模块（子模块继承父包 import 不自动标 `是`）。"
    )
    sections.append("")

    for top in sorted(by_top.keys()):
        mods = sorted(by_top[top], key=lambda x: x.module)
        sections.append(f"### `semantica.{top}`" if top != "(root)" else "### `semantica`（根）")
        sections.append("")
        for inv in mods:
            names = inv.public_names()
            if not names and not inv.classes and not inv.functions:
                sections.append(f"- `{inv.module}` — （无顶层公开符号或未解析 `__all__`）")
                continue
            mod_hit = "是" if _basis_hits_module(usage, inv.module) else "否"
            sections.append(
                f"- **`{inv.module}`** (`{inv.source_relpath}`) — Basis import 模块：**{mod_hit}**"
            )
            rows: list[list[str]] = []
            for name in names:
                total_symbols += 1
                sym_hit = "是" if _basis_hits_symbol(usage, inv.module, name) else "否"
                kind = "class" if name in inv.classes else "function" if name in inv.functions else "export"
                rows.append([f"`{name}`", kind, sym_hit])
            if rows:
                sections.append("")
                sections.append(_md_table(["符号", "类型", "Basis"], rows))
                sections.append("")
        sections.append("")

    return "\n".join(sections), len(inventories), total_symbols


def main() -> int:
    try:
        import semantica
    except ImportError:
        print("semantica is not installed; run uv sync first", file=sys.stderr)
        return 1

    pkg_root = Path(semantica.__file__).resolve().parent
    inventories = _scan_semantica_package(pkg_root)
    usage = _parse_basis_semantica_usage()

    from semantica.semantic_extract.methods import (
        get_entity_method,
        get_relation_method,
        get_triplet_method,
    )
    from semantica.split.methods import _SPLIT_METHODS
    import semantica.kg as kg_mod
    from semantica.kg import GraphBuilder
    from semantica.export.methods import list_available_methods as list_export
    from semantica.ingest.methods import list_available_methods as list_ingest
    from semantica.reasoning.reasoner import Reasoner
    from semantica.ontology import OntologyEngine

    version = semantica.__version__
    entity_ok = [m for m in ENTITY_METHODS if _ok(get_entity_method, m)]
    relation_ok = [m for m in RELATION_METHODS if _ok(get_relation_method, m)]
    triplet_ok = [m for m in TRIPLET_METHODS if _ok(get_triplet_method, m)]
    split_keys = sorted(_SPLIT_METHODS.keys())
    kg_all = sorted(getattr(kg_mod, "__all__", []))
    reasoner_methods = sorted(m for m in dir(Reasoner) if not m.startswith("_"))
    ontology_methods = sorted(
        m
        for m in dir(OntologyEngine)
        if not m.startswith("_") and callable(getattr(OntologyEngine, m, None))
    )
    top_packages = sorted({m.name for m in pkgutil.iter_modules(semantica.__path__)})

    gb_init = inspect.signature(GraphBuilder.__init__)
    gb_build = inspect.signature(GraphBuilder.build)

    KG_USED_IN_BASIS = frozenset(
        {
            "GraphBuilder",
            "PathFinder",
            "LinkPredictor",
            "SimilarityCalculator",
            "TemporalPatternDetector",
        }
    )

    def basis_uses(fragment: str) -> str:
        return "是" if any(fragment in u for u in usage.raw_lines) else "否"

    kg_rows = []
    for name in kg_all:
        if not name[0].isupper() and name not in ("method_registry", "algorithm_registry"):
            continue
        flag = "是" if name in KG_USED_IN_BASIS else "否"
        kg_rows.append([f"`{name}`", flag])

    full_catalog_md, module_count, symbol_count = _build_full_catalog(inventories, usage)

    entity_methods_md = ", ".join(f"`{m}`" for m in entity_ok)
    relation_methods_md = ", ".join(f"`{m}`" for m in relation_ok)
    triplet_methods_md = ", ".join(f"`{m}`" for m in triplet_ok)
    extract_table = _md_table(
        ["任务", "SDK `*_method`", "Basis"],
        [
            ["实体", entity_methods_md, "间接；产品子集 `pattern` / `ml` / `llm`"],
            ["关系", relation_methods_md, "间接；产品子集同上"],
            ["三元组", triplet_methods_md, "间接；Basis 固定 `extract_triplets=False`"],
        ],
    )
    kg_table = _md_table(["符号", "Basis 直接引用"], kg_rows)
    ontology_methods_md = ", ".join(f"`{m}`" for m in ontology_methods)
    reasoner_methods_md = ", ".join(f"`{m}`" for m in reasoner_methods)
    split_keys_md = "`, `".join(split_keys)
    product_chunk_md = "`, `".join(sorted(PRODUCT_CHUNK))
    export_keys_md = ", ".join(sorted(list_export().keys()))
    ingest_keys_md = ", ".join(sorted(list_ingest().keys()))
    top_packages_md = ", ".join(top_packages)
    imports_block = "\n".join(usage.raw_lines)
    today = date.today().isoformat()

    # Registry detail (import-time)
    export_registry_md = "\n".join(
        f"- `{k}`: {', '.join(f'`{v}`' for v in vals)}"
        for k, vals in sorted(list_export().items())
    )
    ingest_registry_md = "\n".join(
        f"- `{k}`: {', '.join(f'`{v}`' for v in vals)}"
        for k, vals in sorted(list_ingest().items())
    )

    doc = f"""# Semantica SDK 能力地图（代码接口为准）

> **来源**：`scripts/docs/generate-semantica-sdk-capability-map.py` — 安装包路径 `{pkg_root}` + `basis/` import 扫描。  
> **SDK 版本**：`{version}`（与 `uv.lock` 一致时请 `uv sync`）  
> **生成日期**：{today}  
> **全包扫描**：{module_count} 个 Python 模块，约 {symbol_count} 个公开符号（见 [§16](#16-全包公开符号清单ast)）。

重新生成：

```bash
uv run python scripts/docs/generate-semantica-sdk-capability-map.py
```

## 图例（Basis 列）

| 标记 | 含义 |
|------|------|
| **是** | `basis/` 包内直接 `import` / 调用该 SDK 符号 |
| **间接** | 仅通过 `GraphBuilder.build(**kwargs)` 等传入参数触发 `semantic_extract` |
| **否** | SDK 有公开接口，`basis/` 未引用 |
| **产品子集** | OpenAPI/UI 只暴露部分 SDK 合法字符串 |

Basis 以进程内 **`embedded_sdk`** 使用 Semantica（见 `GET /api/v1/platform`），不运行 `semantica server` / Explorer 路由（CI：`audit-semantica-explorer-imports.py`）。

---

## 1. `semantic_extract` — `get_*_method()` 可解析的后端

{extract_table}

**Basis 传入 `GraphBuilder.build` 的 kwargs**（`basis/domain/knowledge/pipeline/extract_kwargs.py`）：  
`extract`, `ner_method`, `relation_method`, `extract_relations`, `extract_triplets`, `model`（spaCy）, `provider` / `api_key` / `llm_model` / `base_url`（`llm` 时）。

`GraphBuilder` 签名（代码）：

- `__init__{gb_init}`
- `build{gb_build}`

文档中还提到：`triplet_method`, `entity_resolver`, `relationships` 等 — Basis **未传**。

---

## 2. `kg` — `semantica.kg.__all__`（包 `__init__` 导出）

{kg_table}

---

## 3. `context`

| SDK | Basis |
|-----|--------|
| `ContextGraph` | {basis_uses("ContextGraph")} |
| `context_graph._resolve_edge_identity` | {basis_uses("_resolve_edge_identity")} |
| `utils.skos`（`is_skos_hierarchy_edge`, `validate_skos_hierarchy`） | {basis_uses("semantica.utils.skos")} |
| `ContextRetriever`, `EntityLinker`, `AgentMemory`, `DecisionContext`, … | 否 |

---

## 4. `ontology` — `OntologyEngine` 方法（`dir()` 可调用）

Basis 实际调用子集：`from_data`, `from_text`, `list_vocabularies`, `search_concepts`, `list_concepts`, `validate`, `validate_graph`, `to_shacl`。

全部可调用方法（代码）：{ontology_methods_md}

| SDK | Basis |
|-----|--------|
| `OntologyIngestor` | {basis_uses("OntologyIngestor")} |

---

## 5. `reasoning` — `Reasoner`

可调用方法：{reasoner_methods_md}

| SDK | Basis |
|-----|--------|
| `infer_facts` | {basis_uses("Reasoner")} |
| `DatalogReasoner`, `SPARQLReasoner`, `ReteEngine`, `GraphReasoner`, … | 否 |

---

## 6. `parse` / `normalize` / `split`

| SDK 入口 | Basis |
|----------|--------|
| `parse.parse_document` | {basis_uses("parse_document")} |
| `normalize.clean_text`, `normalize_text` | {basis_uses("normalize")} |
| `split.TextSplitter` | {basis_uses("TextSplitter")} |

**`split.methods._SPLIT_METHODS` 全部键**（{len(split_keys)} 个）：

`{split_keys_md}`

**Basis 产品允许分块**（`PRODUCT_CHUNK_METHODS`）：`{product_chunk_md}`

---

## 7. `embeddings`

| SDK | Basis |
|-----|--------|
| `embeddings.methods.embed_text(..., method="fallback")` | {basis_uses("embed_text")} |
| 远程 embedding | 否（Basis 使用 `openai` 客户端） |

---

## 8. `vector_store`

| SDK | Basis |
|-----|--------|
| `SQLiteVecStore` | {basis_uses("SQLiteVecStore")} |
| `FAISSStore`, `PgVectorStore`, `QdrantStore`, … | 否（`vectorstore-faiss` extra 已装但未引用） |

---

## 9. `export` — `list_available_methods()`

{export_keys_md}

{export_registry_md}

| SDK | Basis |
|-----|--------|
| `RDFExporter` | {basis_uses("RDFExporter")} |
| `GraphExporter` | {basis_uses("GraphExporter")} |
| 其余 `__all__` exporter / `export_*` | 否 |

---

## 10. `ingest` — `list_available_methods()`

{ingest_keys_md}

{ingest_registry_md}

| SDK | Basis |
|-----|--------|
| `OntologyIngestor` / `ontology` | {basis_uses("OntologyIngestor")} |
| `ingest_file`, `ingest_repository`（git）, `ingest_mcp`, … | 否 |

---

## 11. `deduplication` / `provenance` / `change_management`

| SDK | Basis |
|-----|--------|
| `DuplicateDetector` | {basis_uses("DuplicateDetector")} |
| `provenance.integrity.verify_checksum` | {basis_uses("verify_checksum")} |
| `VersionManager` | {basis_uses("VersionManager")} |
| `ChangeLogEntry` | {basis_uses("ChangeLogEntry")} |

---

## 12. 顶层包（`pkgutil.iter_modules(semantica)`）

{top_packages_md}

| 包 | Basis |
|----|--------|
| `llms.*` | 否（LLM 抽取经 `GraphBuilder` + OpenAI 兼容 kwargs） |
| `explorer`, `server`, `cli`, `mcp_server`, `worker` | 否 |
| `conflicts`, `evals`, `visualization`, `triplet_store`, `graph_store`, `pipeline`, `core`, `seed` | 否 |

---

## 13. `basis/` 内 Semantica import 清单（扫描结果）

```
{imports_block}
```

---

## 14. Basis 默认 `semantica[...]` extras（`pyproject.toml`）

`documents`, `parse-pdf`, `nlp-spacy`, `llm-openai`, `embeddings-local`, `vectorstore-faiss`, `vectorstore-sqlite`, `shacl`, `split-tiktoken`, `ingest-git`

可选：`heavy`（docling、pgvector、litellm、neo4j）、`explorer`（上游 Explorer CLI）。

---

## 15. 相关代码索引

| 能力 | Basis 路径 |
|------|------------|
| 文档抽取管道 | `basis/domain/knowledge/pipeline/document.py`, `extract_kwargs.py`, `file_ingest.py`, `chunk_split.py` |
| 图会话 / 探索 | `basis/domain/graph/projection/session.py`, `basis/domain/graph/session/basis_graph_session.py` |
| 本体 / SHACL | `basis/domain/ontology/hub/*`, `basis/domain/ontology/browse/*`, `basis/domain/ontology/shacl/*` |
| 推理 | `basis/domain/graph/reasoning/run.py` |
| 搜索向量 | `basis/domain/knowledge/search/embeddings.py`, `vector_index.py` |
| 导出 | `basis/domain/graph/reads/export_read.py` |
| 平台版本 | `basis/interface/http/platform/platform_info.py` |

---

## 16. 全包公开符号清单（AST）

{full_catalog_md}
"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({module_count} modules, ~{symbol_count} symbols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
