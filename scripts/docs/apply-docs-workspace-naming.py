#!/usr/bin/env python3
"""One-off friendly: normalize legacy kb naming in local docs/**/*.md (docs/ is gitignored)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"

# Longest / most specific replacements first.
REPLACEMENTS: list[tuple[str, str]] = [
    ("/kbs/:kbId", "/workspaces/:workspaceId"),
    ("/kbs/{kbId}", "/workspaces/{workspaceId}"),
    ("/kbs/{workspace_id}", "/workspaces/{workspace_id}"),
    ("KB_NAV_BY_ZONE", "WORKSPACE_NAV_BY_ZONE"),
    ("kb_graph_staging_sessions", "workspace_graph_staging_sessions"),
    ("kb_connector_policies", "connector_policies"),
    ("kb_connections", "connector_connections"),
    ("kb_oauth_configs", "connector_oauth_configs"),
    ("kb_connector_runs", "connector_runs"),
    ("kb_members", "members"),
    ("BasisKbGraphSession", "BasisGraphSession"),
    ("KbGraphSessionRegistry", "GraphSessionRegistry"),
    ("KbGraphRuntime", "GraphRuntime"),
    ("kb_graph_runtime_for", "graph_runtime_for"),
    ("require_kb_graph_session", "require_graph_session"),
    ("build_kb_graph_adapter", "build_graph_adapter"),
    ("basis_kb_graph_session", "basis_graph_session"),
    ("basis-v1-kb.json", "basis-v1-workspaces.json"),
    ("basis-kb-mcp", "basis-workspace-mcp"),
    ("KbExplorerRuntime", "GraphRuntime"),
    ("KbLineageWorkspace", "Lineage workspace module"),
    ("KbMember", "Member"),
    ("KbProcessingOptionsSnapshot", "ProcessingOptionsSnapshot"),
    ("kb_core_context.py", "core_context.py"),
    ("kb_connectors.py", "connectors.py"),
    ("kb_sources.py", "sources.py"),
    ("kb_entities.py", "ledger / entities routes"),
    ("kb_review.py", "review.py"),
    ("kb_graph_staging.py", "graph_staging.py"),
    ("kb_graph_session_routes.py", "graph_session_routes.py"),
    ("kb_graph_*.py", "graph_*.py"),
    ("kb_connectors*.py", "connectors*.py"),
    ("kb_governance_configs", "governance_configs"),
    ("kb_ontology_hub_*", "ontology_hub_*"),
    ("kb_ontology_*", "ontology_*"),
    ("kb_documents.py", "documents.py"),
    ("kb_ledger.py", "ledger.py"),
    ("kb_mappings.py", "config_mappings.py"),
    ("kb_alerts.py", "config_alerts.py"),
    ("kb_tokens.py", "tokens.py"),
    ("kb_reasoning_rules.py", "config_reasoning_rules.py"),
    ("kb_e2e_helpers.py", "e2e_helpers.py"),
    ("kbs.py", "resources.py"),
    ("kb_graph.py", "graph.py"),
    ("kb_ontology.py", "ontology.py"),
    ("GET .../kbs/{workspace_id}", "GET .../workspaces/{workspace_id}"),
    ("test_kb_graph_session_routes.py", "test_graph_session_routes.py"),
    ("test_kb_alerts_emit.py", "test_workspace_alerts_emit.py"),
    ("test_kb_review.py", "test_workspace_review.py"),
    ("audit-kb-http-aggregators.py", "audit-workspace-http-aggregators.py"),
    ("list_audit_for_kb", "list_audit_for_workspace"),
    ("kb.graph.", "workspace.graph."),
    ("`kbs` table", "`workspaces` table"),
    (", KBs,", ", workspaces,"),
    (" KBs,", " workspaces,"),
    ("| `kb.read`", "| workspace read (viewer+)"),
    ("| `kb.write`", "| workspace write (editor+)"),
    ("`kb.read`", "workspace read"),
    ("`kb.write`", "workspace write"),
    ("`kb.review`", "workspace review (editor+)"),
]


def main() -> int:
    if not DOCS.is_dir():
        print("docs/ not found — skip")
        return 0
    pairs = sorted(REPLACEMENTS, key=lambda x: len(x[0]), reverse=True)
    changed = 0
    for path in sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        new = text
        for old, sub in pairs:
            new = new.replace(old, sub)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
            print(path.relative_to(ROOT))
    print(f"updated {changed} markdown files under docs/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
