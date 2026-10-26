"""MCP tools/list descriptions (inputSchema from BC schemas via tool_catalog.run)."""

from __future__ import annotations

from typing import Any

MCP_TOOL_METADATA: dict[str, dict[str, Any]] = {
    "list_processing_jobs": {"description": "List document processing jobs (extract, chunk, project)."},
    "reset_workspace": {
        "description": (
            "Reset workspace data while keeping workspace id, members, and settings. "
            "preview=true returns counts, default_scopes, available_scopes, and export_pack_path. "
            "Otherwise pass confirmation=workspace name (exact) and optional scopes[] "
            "(knowledge, graph, connectors, reasoning, governance; default omits governance). "
            "async=true (default) enqueues jobs.kind=workspace_reset—poll via list_processing_jobs; "
            "async=false runs inline. Owner only. Do not use delete_node loops to clear a workspace."
        )
    },
    "search_chunks": {
        "description": (
            "Search document chunks (RAG citations). Use chunk_id from results with propose_remember or optional "
            "chunk_id on graph/extract tools. See MCP resource semantica://guide/evidence."
        )
    },
    "get_chunk": {
        "description": "Fetch one chunk by id (from search_chunks). Use before cite or when extract_* needs full text."
    },
    "entity_facts": {"description": "Open statements and inference-derived facts for a ledger entity id (derived_facts include proof-chain premises)."},
    "list_derived_facts": {"description": "List reasoning-derived facts in the ledger (optionally scoped to one entity). Use after rules/inference to read conclusions not present in source documents."},
    "list_typed_facts": {"description": "List ontology-typed facts materialized from confirmed mappings (predicate URIs such as commercialContact, not raw document text)."},
    "list_mappings": {"description": "List statement-to-ontology mapping proposals (signature, target_uri, status)."},
    "list_surface_phrases": {
        "description": "List distinct surface phrases seen in the ledger (for mapping signature suggestions)."
    },
    "list_entity_type_object_labels": {
        "description": (
            "List rdf:type object labels from typed facts plus configured entity-type surface phrases "
            "(class mapping hints)."
        )
    },
    "assign_entity_types": {
        "description": (
            "Assign rdf:type to subjects directly (batch). Each item: subject_id (ledger entity or graph "
            "node id) + class_uri. Rebuilds graph projection when facts are created. Editor write."
        )
    },
    "clear_entity_types": {
        "description": (
            "Invalidate active rdf:type typed_facts for subjects (batch subject_ids). "
            "Rebuilds graph projection when any facts are cleared. Editor write."
        )
    },
    "invalidate_entities": {
        "description": (
            "Soft-invalidate ledger entities (batch entity_ids): sets invalidated_at on the entity "
            "and on related statements, typed_facts, and derived_facts. Rebuilds graph projection. "
            "Prefer over delete_node for removing business entities from the canonical ledger. Editor write."
        )
    },
    "delete_document": {
        "description": (
            "Hard-delete a document and its chunks, vectors, and ledger rows tied only to that document "
            "(same semantics as HTTP DELETE …/documents/{document_id}). document_id may be UUID or doc_id. "
            "Rebuilds graph projection. Editor write."
        )
    },
    "delete_entity": {
        "description": (
            "Hard-delete a ledger entity and its statements, typed/derived facts, and related rows "
            "(HTTP DELETE …/ledger/entities/{entity_id}). Irreversible; prefer invalidate_entities for "
            "soft temporal removal. Rebuilds graph projection. Editor write."
        )
    },
    "propose_mapping": {
        "description": (
            "Create a statement-to-ontology mapping (proposed or confirmed), or direct class assignment when "
            "subject_id + target_kind class + target_uri are set (no signature). Confirmed requires editor. "
            "Same semantics as HTTP POST …/mappings for signature-based rows."
        )
    },
    "update_mapping_status": {
        "description": (
            "Confirm, reject, or supersede a mapping (editor). Materializes typed facts on confirm. "
            "Same semantics as HTTP POST …/mappings/{mapping_id}/status."
        )
    },
    "list_ontology_registry": {"description": "List ontologies in the workspace hub registry (optional q and status filters)."},
    "get_ontology_graph": {"description": "Fetch scoped class/property/individual graph for one ontology URI from the hub."},
    "search_ontology_entities": {
        "description": "Search ontology hub entities by keyword (class, property, individual, concept, scheme)."
    },
    "save_ontology_draft": {
        "description": (
            "Save an ontology editor draft diff (editor). Persists hub sidecar; does not publish. "
            "diff keys: added_classes, added_properties, added_individuals, added_edges "
            "(source, target, type e.g. rdfs:subClassOf|rdfs:domain|rdfs:range), added_axioms "
            "(type subClassOf or rdfs:subClassOf; subject + object), modified_classes "
            "(label; or subClassOf/superclass/parent for hierarchy), modified_properties "
            "(label; or domain/range). Unknown keys are ignored. "
            "Use submit_ontology_proposal to open governance review."
        )
    },
    "list_ontology_drafts": {
        "description": "List saved ontology editor drafts for one ontology URI (newest-first order not guaranteed)."
    },
    "get_ontology_draft": {"description": "Fetch one ontology editor draft by draft_id."},
    "submit_ontology_proposal": {
        "description": (
            "Submit a saved draft as a governance proposal (editor). Same flow as HTTP POST …/ontology/proposals."
        )
    },
    "list_ontology_proposals": {"description": "List ontology governance proposals (optional ontology_uri and state filters)."},
    "get_ontology_proposal": {"description": "Fetch one ontology governance proposal by id (from list_ontology_proposals)."},
    "approve_ontology_proposal": {
        "description": "Approve a proposed ontology change (editor). Same semantics as HTTP POST …/ontology/proposals/{id}/approve."
    },
    "reject_ontology_proposal": {
        "description": "Reject a proposed ontology change (editor). Same semantics as HTTP POST …/ontology/proposals/{id}/reject."
    },
    "publish_ontology_proposal": {
        "description": (
            "Publish an approved proposal into the workspace graph (editor). Applies draft diff and records a version. "
            "Same semantics as HTTP POST …/ontology/proposals/{id}/publish."
        )
    },
    "comment_ontology_proposal": {
        "description": "Add a review comment on an ontology proposal (editor). Same semantics as HTTP POST …/ontology/proposals/{id}/comment."
    },
    "list_ontology_versions": {
        "description": "List published ontology versions for one ontology URI (from publish_ontology_proposal)."
    },
    "compare_ontology_versions": {
        "description": (
            "Compare two published ontology versions (version1, version2). "
            "Same semantics as HTTP POST …/ontology/versions/{ontology_uri}/compare."
        )
    },
    "restore_ontology_version_draft": {
        "description": (
            "Create an editor draft that restores the published head toward target_version "
            "(diff from latest published to target). Does not publish; submit via "
            "submit_ontology_proposal. Editor write."
        )
    },
    "toggle_ontology": {
        "description": (
            "Toggle enabled flag for an ontology registry entry (editor). Disabled ontologies are "
            "omitted from explorer graph projection on rebuild. Same semantics as HTTP PATCH …/ontology/{uri}/toggle."
        )
    },
    "get_statement": {"description": "Resolve a ledger statement id to subject/object, predicate, and evidence (for tracing premises behind derived facts)."},
    "propose_remember": {
        "description": (
            "Propose a new canonical fact for human review (pending statement). "
            "Does not write to the graph until approved. Optional chunk_id and quote bind ledger evidence. "
            "For structured rdf:type (subject → class), use assign_entity_types instead."
        )
    },
    "paths": {"description": "Shortest path between two graph node ids."},
    "list_rules": {"description": "List forward-chaining reasoning rules in the workspace rule library (name, body, enabled)."},
    "get_rule": {"description": "Fetch one reasoning rule by id (from list_rules)."},
    "run_reasoning": {
        "description": (
            "Run forward-chaining reasoning. Omit facts to use ontology typed_facts (ground_facts in the response). "
            "Set apply_to_graph true (editor) to persist inferred edges and derived facts. "
            "Optional chunk_id and quote attach basis_evidence on inferred edges and appear in evidence when set."
        )
    },
    "list_review_items": {"description": "List human review queue items (merges, imports, remember proposals, conflicts)."},
    "get_review_item": {"description": "Fetch one review queue item by id."},
    "approve_review_item": {"description": "Approve any open review queue item (merges, imports, remember, conflicts, writeback, …). Same semantics as HTTP POST .../review/items/{item_id}/approve."},
    "reject_review_item": {"description": "Reject any open review queue item. Same semantics as HTTP POST .../review/items/{item_id}/reject."},
    "list_connector_catalog": {
        "description": (
            "List BOCP connector services allowed for this workspace (summary rows; same filters as "
            "HTTP GET …/connectors/catalog for query/limit/has_streams_only — HTTP may return full manifests)."
        )
    },
    "describe_connector_service": {
        "description": (
            "Describe one connector service (catalog summary plus stream/tool slices; HTTP GET "
            "…/connectors/catalog/{service} returns the full manifest document)."
        )
    },
    "list_connector_connections": {
        "description": (
            "List saved BOCP connections (compact rows; HTTP GET …/connectors/connections returns "
            "the same vault rows with extra console fields such as connection_config and has_credentials)."
        )
    },
    "upsert_connector_connection": {
        "description": (
            "Create or update a saved BOCP connection (encrypted vault). Same semantics as HTTP PUT "
            "…/connectors/connections/{service}."
        )
    },
    "delete_connector_connection": {
        "description": (
            "Delete a saved BOCP connection. Same semantics as HTTP DELETE "
            "…/connectors/connections/{service}."
        )
    },
    "check_connector_connection": {
        "description": (
            "Validate credentials and return connector profile metadata. Same semantics as HTTP POST "
            "…/connectors/connections/{service}/check."
        )
    },
    "discover_connector_schema": {
        "description": (
            "Discover stream or SQL table schema for a saved connection. Same semantics as HTTP GET "
            "…/connectors/connections/{service}/discover."
        )
    },
    "list_connector_table_mappings": {
        "description": (
            "List stream-to-ontology table mappings (paginated summary; HTTP GET …/table-mappings "
            "returns full mapping records for the workspace console)."
        )
    },
    "sync_connector_table_mapping": {"description": "Run inbound BOCP sync for one table mapping (pull external rows into the Evidence Ledger)."},
    "invoke_connector_primitive": {"description": "Invoke a BOCP Section 10 primitive for an entity or procedure action (discover, list, mutate, invoke) using manifest operations — no table mapping required."},
    "execute_connector_tool": {"description": "Execute a standalone BOCP ToolSpec RPC for an allowed provider (subject to workspace action_policy_json)."},
    "propose_entity_writeback": {"description": "Propose an outbound writeback of ledger entity attributes to its external BOCP connector stream (creates an entity_sync_outbox record and a human review gate when writeback_mode is 'review')."},
    "extract_entities": {
        "description": (
            "Extract named entities (people, places, organisations, concepts) from text using Semantica NER. "
            "Provide text or chunk_id (ledger chunk); optional quote. Response may include evidence when chunk_id is set."
        )
    },
    "extract_relations": {
        "description": (
            "Extract relations and (subject, predicate, object) triplets from text. "
            "Provide text or chunk_id; optional quote. Response may include evidence when chunk_id is set."
        )
    },
    "record_decision": {
        "description": (
            "Record a decision into the workspace knowledge graph with full context, causal links, and metadata. "
            "Optional chunk_id and quote attach basis_evidence on the decision."
        )
    },
    "query_decisions": {
        "description": "Query recorded decisions by natural language, category, or get all recent decisions."
    },
    "find_precedents": {
        "description": "Find past decisions similar to a given scenario using hybrid similarity search."
    },
    "get_causal_chain": {
        "description": "Trace the causal chain upstream or downstream from a decision."
    },
    "add_entity": {
        "description": (
            "Add a node/entity to the workspace knowledge graph. "
            "Optional chunk_id and quote store basis_evidence in node metadata (graph write; not ledger propose_remember)."
        )
    },
    "add_relationship": {
        "description": (
            "Add a directed relationship (edge) between two entities in the knowledge graph. "
            "Optional chunk_id and quote store basis_evidence on the edge metadata."
        )
    },
    "get_graph_analytics": {
        "description": "Compute PageRank centrality and community detection over the knowledge graph."
    },
    "export_graph": {
        "description": "Export the current knowledge graph. Formats: turtle, ttl, nt, xml, json-ld, json, csv, graphml."
    },
    "get_graph_summary": {
        "description": (
            "Workspace and graph summary: ledger entity/document counts plus projection node_count (total), "
            "node_count_active, node_count_archived, edge_count, decision_count, graph_ready."
        )
    },
    "query_graph": {
        "description": (
            "Query the graph or ledger: mode node | neighbors | search (graph) | entities (ledger). "
            "Neighbors/search omit projection nodes with status=archived unless include_archived=true."
        )
    },
    "update_node": {
        "description": (
            "Update properties of an existing node (e.g. mark an action todo/doing/done with a note). "
            "Optional chunk_id, quote, and rationale are recorded in metadata and audit."
        )
    },
    "delete_node": {
        "description": (
            "Archive a projection graph node (status='archived' on the snapshot only; does not invalidate "
            "ledger entities or statements). node_count_active drops; node_count total unchanged. "
            "Full graph rebuild from ledger restores entities without the archive mark. "
            "Optional chunk_id, quote, and rationale attach evidence before archive."
        )
    },
}
