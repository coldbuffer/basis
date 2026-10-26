"""Semantica MCP–aligned workspace tool handlers."""

from __future__ import annotations

import json
from typing import Any

from basis.application.kernel import WorkspaceCoreContext
from basis.application.semantica_compat.graph_access import (
    context_graph,
    persist_graph_session,
    require_graph_mutation,
)
from basis.domain.graph.governance.decisions_read import get_causal_chain as basis_decision_chain
from basis.domain.graph.governance.decisions_read import list_decisions
from basis.application.graph import operations as graph_ops
from basis.application.workspace import operations as workspace_ops
from basis.domain.errors import AdminError
from basis.domain.graph.reads.export_read import export_graph as export_graph_content
from basis.domain.graph.reads.read import get_node
from basis.domain.graph.session.guard import require_graph_session
from basis.application.evidence import (
    optional_evidence_attestation,
    optional_metadata_with_evidence,
    resolve_extract_text,
)
from basis.domain.knowledge.services.graph_audit import audit_graph


def op_extract_entities(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    text, extra = resolve_extract_text(ctx, args)
    if text is None:
        return extra
    from semantica.semantic_extract import NamedEntityRecognizer

    init_kwargs: dict[str, Any] = {}
    for key in ("model", "language", "confidence_threshold"):
        if args.get(key) is not None:
            init_kwargs[key] = args[key]
    method = str(args.get("method") or "ml")
    ner = NamedEntityRecognizer(methods=[method], **init_kwargs)
    entities = ner.extract_entities(text) or []
    payload: dict[str, Any] = {
        "entities": [
            {
                "text": getattr(entity, "text", ""),
                "label": getattr(entity, "label", ""),
                "type": getattr(entity, "label", None),
                "start": getattr(entity, "start_char", getattr(entity, "start", None)),
                "end": getattr(entity, "end_char", getattr(entity, "end", None)),
                "confidence": getattr(entity, "confidence", 1.0),
            }
            for entity in entities
        ],
    }
    if extra.get("chunk_id"):
        payload["evidence"] = extra
    return payload


def op_extract_relations(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    text, extra = resolve_extract_text(ctx, args)
    if text is None:
        return extra
    from semantica.semantic_extract import NamedEntityRecognizer, RelationExtractor, TripletExtractor

    rel_kwargs: dict[str, Any] = {}
    ner_kwargs: dict[str, Any] = {}
    for key in ("model", "language"):
        if args.get(key) is not None:
            rel_kwargs[key] = args[key]
            ner_kwargs[key] = args[key]
    method = str(args.get("method") or "pattern")
    entities = NamedEntityRecognizer(methods=["ml"], **ner_kwargs).extract_entities(text) or []
    relations = RelationExtractor(method=method, **rel_kwargs).extract_relations(text, entities)
    triplets = TripletExtractor().extract_triplets(text)
    payload: dict[str, Any] = {
        "relations": [
            {
                "source": getattr(rel, "source", None),
                "type": getattr(rel, "type", None),
                "target": getattr(rel, "target", None),
            }
            for rel in (relations or [])
        ],
        "triplets": [
            {
                "subject": getattr(triplet, "subject", None),
                "predicate": getattr(triplet, "predicate", None),
                "object": getattr(triplet, "object", None),
            }
            for triplet in (triplets or [])
        ],
    }
    if extra.get("chunk_id"):
        payload["evidence"] = extra
    return payload


def _session(ctx: WorkspaceCoreContext) -> Any:
    runtime = ctx.graph_runtime()
    return require_graph_session(runtime)


def op_record_decision(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    graph = require_graph_mutation(ctx)
    if not hasattr(graph, "record_decision"):
        return {"error": "graph does not support record_decision"}
    attestation, err = optional_evidence_attestation(ctx, args)
    if err:
        return err
    metadata: dict[str, Any] = {}
    if attestation:
        metadata["basis_evidence"] = dict(attestation)
    decision_id = graph.record_decision(
        category=args["category"],
        scenario=args["scenario"],
        reasoning=args["reasoning"],
        outcome=args["outcome"],
        confidence=float(args["confidence"]),
        entities=args.get("entities") or [],
        decision_maker=args.get("decision_maker") or "mcp_client",
        valid_from=args.get("valid_from"),
        valid_until=args.get("valid_until"),
        metadata=metadata or None,
    )
    persist_graph_session(ctx)
    audit_extra: dict[str, Any] = {"decision_id": str(decision_id)}
    if attestation:
        audit_extra["chunk_id"] = attestation["chunk_id"]
    audit_graph(
        ctx.store,
        ctx.user,
        ctx.workspace.id,
        "workspace.graph.record_decision",
        extra=audit_extra,
    )
    out: dict[str, Any] = {"decision_id": decision_id, "status": "recorded"}
    if attestation:
        out["evidence"] = dict(attestation)
    return out


def op_query_decisions(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    category = args.get("category")
    limit = int(args.get("limit", 10))
    graph = context_graph(ctx)
    try:
        if query and hasattr(graph, "find_similar_decisions"):
            results = graph.find_similar_decisions(query, max_results=limit, min_similarity=0.05)
            decisions = results if isinstance(results, list) else list(results)
        elif category:
            session = _session(ctx)
            decisions = list_decisions(session, category=str(category), skip=0, limit=limit)
        else:
            session = _session(ctx)
            decisions = list_decisions(session, category=None, skip=0, limit=limit)
        return {"decisions": decisions}
    except Exception as exc:
        return {"error": str(exc), "decisions": []}


def op_find_precedents(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    scenario = str(args.get("scenario", "")).strip()
    if not scenario:
        return {"error": "scenario is required"}
    max_results = int(args.get("max_results", 5))
    min_similarity = float(args.get("min_similarity", 0.05))
    graph = context_graph(ctx)
    if not hasattr(graph, "find_similar_decisions"):
        return {"error": "find_similar_decisions unavailable", "precedents": []}
    try:
        precedents = graph.find_similar_decisions(
            scenario,
            max_results=max_results,
            min_similarity=min_similarity,
        )
        return {
            "precedents": precedents if isinstance(precedents, list) else list(precedents),
        }
    except Exception as exc:
        return {"error": str(exc), "precedents": []}


def op_get_causal_chain(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    decision_id = str(args.get("decision_id", "")).strip()
    if not decision_id:
        return {"error": "decision_id is required"}
    direction = str(args.get("direction") or "downstream")
    max_depth = int(args.get("max_depth", 5))
    graph = context_graph(ctx)
    try:
        from semantica.context.causal_analyzer import CausalChainAnalyzer
        from semantica.context.decision_models import serialize_decision

        analyzer = CausalChainAnalyzer(graph_store=graph)
        chain = analyzer.get_causal_chain(decision_id, direction=direction, max_depth=max_depth)
        serialized = []
        for item in chain:
            if hasattr(item, "to_dict"):
                serialized.append(json.loads(serialize_decision(item)))
            else:
                serialized.append(item)
        return {"chain": serialized}
    except Exception:
        try:
            session = _session(ctx)
            payload = basis_decision_chain(session, decision_id)
            return {"chain": payload.get("chain", [])}
        except Exception as exc:
            return {"error": str(exc), "chain": []}


def op_add_entity(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    node_id = str(args.get("id", "")).strip()
    if not node_id:
        return {"error": "id is required"}
    label = str(args.get("label") or node_id)
    node_type = str(args.get("type") or "Entity")
    metadata = args.get("metadata") or {}
    if not isinstance(metadata, dict):
        return {"error": "metadata must be an object"}
    metadata, evidence, err = optional_metadata_with_evidence(ctx, args, metadata)
    if err:
        return err
    graph = require_graph_mutation(ctx)
    graph.add_node(node_id, node_type, content=label, **metadata)
    persist_graph_session(ctx)
    audit_extra: dict[str, Any] = {"node_id": node_id}
    if evidence:
        audit_extra["chunk_id"] = evidence["chunk_id"]
    audit_graph(
        ctx.store,
        ctx.user,
        ctx.workspace.id,
        "workspace.graph.add_entity",
        extra=audit_extra,
    )
    out: dict[str, Any] = {"status": "added", "id": node_id}
    if evidence:
        out["evidence"] = dict(evidence)
    return out


def op_add_relationship(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    source = str(args.get("source", "")).strip()
    target = str(args.get("target", "")).strip()
    rel_type = str(args.get("type") or "RELATED_TO")
    if not source or not target:
        return {"error": "source and target are required"}
    metadata = args.get("metadata") or {}
    if not isinstance(metadata, dict):
        return {"error": "metadata must be an object"}
    metadata, evidence, err = optional_metadata_with_evidence(ctx, args, metadata)
    if err:
        return err
    graph = require_graph_mutation(ctx)
    graph.add_edge(source, target, rel_type, **metadata)
    persist_graph_session(ctx)
    audit_extra: dict[str, Any] = {"source": source, "target": target, "type": rel_type}
    if evidence:
        audit_extra["chunk_id"] = evidence["chunk_id"]
    audit_graph(
        ctx.store,
        ctx.user,
        ctx.workspace.id,
        "workspace.graph.add_relationship",
        extra=audit_extra,
    )
    out: dict[str, Any] = {"status": "added", "source": source, "target": target, "type": rel_type}
    if evidence:
        out["evidence"] = dict(evidence)
    return out


def op_get_graph_analytics(ctx: WorkspaceCoreContext, _args: dict[str, Any]) -> dict[str, Any]:
    graph = context_graph(ctx)
    try:
        from semantica.kg import CentralityCalculator, CommunityDetector

        centrality = CentralityCalculator().calculate_pagerank(graph)
        communities = CommunityDetector().detect_communities(graph)
        node_count = len(list(graph.find_nodes()))
        edge_count = getattr(graph, "edge_count", lambda: len(list(graph.find_edges())))()
        top_items = sorted(
            centrality.items() if hasattr(centrality, "items") else [],
            key=lambda item: item[1],
            reverse=True,
        )[:10]
        community_count = len(communities) if isinstance(communities, (list, dict)) else 0
        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "top_nodes_by_pagerank": top_items,
            "community_count": community_count,
        }
    except Exception as exc:
        return {"error": str(exc)}


def op_export_graph(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    fmt = str(args.get("format") or "json-ld")
    session = _session(ctx)
    try:
        content, _media, _ext = export_graph_content(session, format=fmt)
    except AdminError as exc:
        return {"error": exc.message}
    except Exception as exc:
        return {"error": str(exc)}
    return {"format": fmt, "data": content}


def op_get_graph_summary(ctx: WorkspaceCoreContext, _args: dict[str, Any]) -> dict[str, Any]:
    from basis.domain.graph.reads.projection_visibility import count_projection_nodes

    workspace_summary = workspace_ops.op_describe_workspace(ctx, {})
    graph = context_graph(ctx)
    try:
        runtime = ctx.graph_runtime()
        total_nodes, active_nodes, archived_nodes = count_projection_nodes(runtime)
        decisions = graph.find_nodes(node_type="decision")
        decision_count = len(list(decisions))
        stats = runtime.basis.stats()
        return {
            **workspace_summary,
            "node_count": total_nodes,
            "node_count_active": active_nodes,
            "node_count_archived": archived_nodes,
            "edge_count": stats.get("edge_count", 0),
            "decision_count": decision_count,
            "graph_ready": True,
        }
    except Exception as exc:
        return {**workspace_summary, "error": str(exc), "graph_ready": False}


def op_query_graph(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    mode = str(args.get("mode") or "neighbors")
    try:
        if mode == "node":
            node_id = str(args.get("node_id") or "").strip()
            if not node_id:
                return {"error": "node_id is required"}
            runtime = ctx.graph_runtime()
            node = get_node(runtime, node_id)
            return {"node": node}

        if mode == "neighbors":
            node_id = str(args.get("node_id") or "").strip()
            if not node_id:
                return {"error": "node_id is required"}
            depth = min(max(int(args.get("depth", 1)), 1), 5)
            payload = graph_ops.op_neighbors(
                ctx,
                {
                    "node_id": node_id,
                    "depth": depth,
                    "include_archived": bool(args.get("include_archived")),
                },
            )
            if "error" in payload:
                return payload
            return {
                "node_id": node_id,
                "depth": depth,
                "neighbors": list(payload.get("neighbors") or []),
            }

        if mode == "search":
            query = str(args.get("query") or "").strip()
            if not query:
                return {"error": "query is required"}
            limit = int(args.get("limit", 50))
            payload = graph_ops.op_graph_search(
                ctx,
                {
                    "query": query,
                    "limit": limit,
                    "include_archived": bool(args.get("include_archived")),
                },
            )
            if "error" in payload:
                return payload
            results = payload.get("results") or []
            return {"query": query.lower(), "results": results, "total": len(results)}

        if mode == "entities":
            query = str(args.get("query") or "").strip()
            if not query:
                return {"error": "query is required"}
            limit = int(args.get("limit", 20))
            return graph_ops.op_find_entities(ctx, {"query": query, "limit": limit})

        return {"error": f"unknown mode '{mode}': use node|neighbors|search|entities"}
    except Exception as exc:
        return {"error": str(exc)}


def op_update_node(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    node_id = str(args.get("node_id") or "").strip()
    properties = args.get("properties")
    if not node_id:
        return {"error": "node_id is required"}
    if not isinstance(properties, dict) or not properties:
        return {"error": "properties (non-empty object) is required"}
    patch = dict(properties)
    rationale = str(args.get("rationale") or "").strip() or None
    merged_meta, evidence, err = optional_metadata_with_evidence(ctx, args, {})
    if err:
        return err
    if merged_meta.get("basis_evidence"):
        be = dict(merged_meta["basis_evidence"])
        if rationale:
            be["rationale"] = rationale
        patch["basis_evidence"] = be
    elif rationale:
        patch["basis_rationale"] = rationale
    graph = require_graph_mutation(ctx)
    if not graph.find_node(node_id):
        return {"error": f"node '{node_id}' not found"}
    if hasattr(graph, "add_node_attribute"):
        graph.add_node_attribute(node_id, patch)
    else:
        graph.add_node(node_id, "entity", **patch)
    persist_graph_session(ctx)
    audit_extra: dict[str, Any] = {"node_id": node_id}
    if evidence:
        audit_extra["chunk_id"] = evidence["chunk_id"]
    if rationale:
        audit_extra["rationale"] = rationale
    audit_graph(
        ctx.store,
        ctx.user,
        ctx.workspace.id,
        "workspace.graph.update_node",
        extra=audit_extra,
    )
    updated = graph.find_node(node_id) or {}
    meta = updated.get("metadata") if isinstance(updated, dict) else {}
    out: dict[str, Any] = {
        "status": "updated",
        "node_id": node_id,
        "properties": {key: (meta or {}).get(key) for key in properties},
        "persisted": ctx.persist_graph is not None,
    }
    if evidence:
        out["evidence"] = dict(evidence)
    return out


def op_delete_node(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    node_id = str(args.get("node_id") or "").strip()
    if not node_id:
        return {"error": "node_id is required"}
    graph = require_graph_mutation(ctx)
    if not graph.find_node(node_id):
        return {"error": f"node '{node_id}' not found"}
    archive_patch: dict[str, Any] = {"status": "archived"}
    rationale = str(args.get("rationale") or "").strip() or None
    merged_meta, evidence, err = optional_metadata_with_evidence(ctx, args, {})
    if err:
        return err
    if merged_meta.get("basis_evidence"):
        be = dict(merged_meta["basis_evidence"])
        if rationale:
            be["rationale"] = rationale
        archive_patch["basis_evidence"] = be
    elif rationale:
        archive_patch["basis_rationale"] = rationale
    if hasattr(graph, "add_node_attribute"):
        graph.add_node_attribute(node_id, archive_patch)
    else:
        graph.add_node(node_id, "entity", **archive_patch)
    persist_graph_session(ctx)
    audit_extra: dict[str, Any] = {"node_id": node_id}
    if evidence:
        audit_extra["chunk_id"] = evidence["chunk_id"]
    if rationale:
        audit_extra["rationale"] = rationale
    audit_graph(
        ctx.store,
        ctx.user,
        ctx.workspace.id,
        "workspace.graph.delete_node",
        extra=audit_extra,
    )
    out: dict[str, Any] = {"status": "archived", "node_id": node_id, "persisted": ctx.persist_graph is not None}
    if evidence:
        out["evidence"] = dict(evidence)
    return out
