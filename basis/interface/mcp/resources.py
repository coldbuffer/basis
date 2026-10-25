"""MCP resources/list and resources/read (Semantica URI compatibility)."""

from __future__ import annotations

import json
from typing import Any

from basis.application.evidence_guide import EVIDENCE_AGENT_GUIDE
from basis.application.kernel import WorkspaceCoreContext
from basis.application.semantica_compat import operations as semantica_ops
from basis.application.tool_catalog import TOOL_NAMES
from basis.interface.mcp.tools import SERVER_INFO

# Same URIs as upstream ``semantica-mcp``; workspace scope comes from the MCP HTTP path.
MCP_RESOURCES: list[dict[str, str]] = [
    {
        "uri": "semantica://graph/summary",
        "name": "Graph Summary",
        "description": "High-level statistics about the current workspace knowledge graph",
        "mimeType": "application/json",
    },
    {
        "uri": "semantica://decisions/list",
        "name": "Decisions",
        "description": "List of recorded decisions in the workspace graph",
        "mimeType": "application/json",
    },
    {
        "uri": "semantica://schema/info",
        "name": "Schema Info",
        "description": "Server info, tool list, capabilities, and evidence_guide for agents",
        "mimeType": "application/json",
    },
    {
        "uri": "semantica://guide/evidence",
        "name": "Evidence guide",
        "description": "How ingest, chunks, propose_remember, and graph writes use optional chunk_id/quote",
        "mimeType": "application/json",
    },
]


def list_resources() -> list[dict[str, str]]:
    return list(MCP_RESOURCES)


def read_resource(ctx: WorkspaceCoreContext, uri: str) -> dict[str, Any]:
    if uri == "semantica://graph/summary":
        payload = semantica_ops.op_get_graph_summary(ctx, {})
    elif uri == "semantica://decisions/list":
        payload = semantica_ops.op_query_decisions(ctx, {"limit": 50})
    elif uri == "semantica://schema/info":
        from basis.application.workspace.operations import op_get_capabilities

        caps = op_get_capabilities(ctx, {})
        payload = {
            "name": SERVER_INFO.get("name", "basis-workspace-mcp"),
            "version": SERVER_INFO.get("version", "0.1.0"),
            "workspace_id": ctx.workspace.id,
            "tools": list(TOOL_NAMES),
            "resources": [r["uri"] for r in MCP_RESOURCES],
            "capabilities": caps,
            "evidence_guide": EVIDENCE_AGENT_GUIDE,
        }
    elif uri == "semantica://guide/evidence":
        payload = EVIDENCE_AGENT_GUIDE
    else:
        return {"error": f"Unknown resource URI: {uri}"}

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "application/json",
                "text": text,
            }
        ]
    }
