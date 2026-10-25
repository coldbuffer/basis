"""Agent-facing evidence workflow (MCP resources / schema info)."""

from __future__ import annotations

from typing import Any

# Stable JSON for resources/read and semantica://schema/info.
EVIDENCE_AGENT_GUIDE: dict[str, Any] = {
    "title": "Basis evidence and write paths",
    "version": 1,
    "summary": (
        "The Evidence Ledger (documents → chunks → statements) is canonical. "
        "The knowledge graph and search are projections. "
        "Optional chunk_id and quote on tools cite ledger chunks without changing Semantica-default behavior when omitted."
    ),
    "ingest": {
        "canonical_store": "evidence_ledger",
        "mcp_tools": ["search_chunks", "get_chunk", "list_processing_jobs"],
        "http_note": (
            "Document ingest (upload text, wait for chunking) is exposed on HTTP "
            "POST /api/v1/workspaces/{workspace_id}/documents. After ingest, use search_chunks or get_chunk in MCP."
        ),
        "typical_sequence": [
            "Ingest document (HTTP) or use existing workspace chunks.",
            "search_chunks with a query → take chunk_id from results.",
            "get_chunk to read full chunk text when needed.",
        ],
    },
    "write_paths": {
        "ledger_canonical": {
            "purpose": "Governed facts that enter the ledger after human review.",
            "primary_tools": ["propose_remember", "approve_review_item", "reject_review_item"],
            "evidence_params": ["chunk_id", "quote"],
            "flow": [
                "propose_remember with content and optional chunk_id (and quote).",
                "get_review_item / list_review_items to inspect the queue.",
                "approve_review_item or reject_review_item.",
                "Trace with get_statement, entity_facts, list_typed_facts as needed.",
            ],
            "without_chunk_id": "Uses an agent remember anchor chunk (__basis_agent_remember__) for provenance.",
        },
        "graph_direct": {
            "purpose": "Structured graph mutations (Semantica-aligned); not auto-submitted to the review queue.",
            "primary_tools": [
                "add_entity",
                "add_relationship",
                "update_node",
                "delete_node",
                "record_decision",
                "run_reasoning",
            ],
            "evidence_params": ["chunk_id", "quote", "rationale (update_node, delete_node)"],
            "metadata_key": "basis_evidence",
            "flow": [
                "Optional: resolve chunk_id via search_chunks / get_chunk.",
                "Call graph tool with optional chunk_id and quote.",
                "Evidence is stored on node/edge/decision metadata (basis_evidence) and echoed in tool evidence when present.",
            ],
            "run_reasoning_note": (
                "apply_to_graph=false: dry-run; evidence only in response. "
                "apply_to_graph=true (editor): inferred edges carry basis_evidence; derived facts may be persisted."
            ),
        },
        "semantica_default": {
            "purpose": "Match upstream Semantica MCP when no ledger citation is needed.",
            "note": "Omit chunk_id and quote on all tools; extract_* pass text directly; graph tools behave like Semantica MCP.",
        },
    },
    "extract_and_reason": {
        "tools": ["extract_entities", "extract_relations", "run_reasoning"],
        "text_or_chunk": "Provide text or chunk_id (chunk body used when text omitted).",
        "response_field": "evidence (chunk_id, quote) when chunk_id was supplied.",
    },
    "discovery": {
        "resource": "semantica://guide/evidence",
        "schema_info_field": "evidence_guide",
        "capabilities": "semantica://schema/info includes workspace capabilities from get_capabilities.",
    },
    "markdown": """# Basis evidence for agents

## Two ways to write knowledge

1. **Ledger (canonical)** — `propose_remember` → review → approved statements. Use **`chunk_id`** (and optional **`quote`**) to cite an ingested document chunk.
2. **Graph (projection)** — `add_entity`, `add_relationship`, `update_node`, `delete_node`, `record_decision`, or `run_reasoning` with **`apply_to_graph: true`**. Optional **`chunk_id`** stores **`basis_evidence`** on the mutation; this does **not** create a remember proposal.

## Get a chunk_id

1. Ingest via HTTP `POST .../documents` (MCP has no ingest tool).
2. **`search_chunks`** → `chunk_id` in results, or **`get_chunk`** for full text.

## Defaults

- No `chunk_id`: Semantica-like behavior; remember proposals use the agent anchor chunk.
- **`get_graph_summary`**: workspace + graph counts.
- **`query_graph`**: `mode` `node` | `neighbors` | `search` | `entities`.

Read **`semantica://guide/evidence`** or **`semantica://schema/info`** (`evidence_guide`) for the machine-readable version.
""",
}
