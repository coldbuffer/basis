"""Graph application services."""

from __future__ import annotations

from typing import Any

from basis.services.kernel import WorkspaceCoreContext
from basis.services.kernel import graph_search_max_limit
from basis.services.graph.reads.derived_neighbors import merge_derived_fact_neighbors
from basis.services.graph.reads.graph_neighbors_merge import merge_session_edge_neighbors
from basis.services.graph.reads.read import find_path, list_neighbors, search_nodes


def op_graph_search(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "query is required"}
    limit = int(args.get("limit", 20))
    max_limit = graph_search_max_limit(ctx, args, limit)
    at = str(args.get("at") or "").strip() or None
    include_archived = bool(args.get("include_archived"))
    runtime = ctx.graph_runtime()
    results = search_nodes(
        runtime,
        query=query,
        limit=limit,
        max_limit=max_limit,
        at=at,
        include_archived=include_archived,
    )
    engine = "explorer" if runtime.adapter is not None else "snapshot"
    payload: dict[str, Any] = {"results": results, "engine": engine}
    if at:
        payload["at"] = at
        payload["temporal_filter"] = True
    return payload


def op_find_entities(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "query is required"}
    limit = int(args.get("limit", 20))
    entities = ctx.knowledge.find_entities(ctx.workspace.id, query=query, limit=limit)
    graph_hits = search_nodes(ctx.graph_runtime(), query=query, limit=limit)
    return {
        "query": query,
        "ledger_entities": entities,
        "graph_nodes": graph_hits,
    }


def op_neighbors(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    node_id = str(args.get("node_id", "")).strip()
    if not node_id:
        return {"error": "node_id is required"}
    depth = int(args.get("depth", 1))
    include_archived = bool(args.get("include_archived"))
    runtime = ctx.graph_runtime()
    neighbors = list_neighbors(
        runtime,
        node_id,
        depth=depth,
        include_archived=include_archived,
    )
    neighbors = merge_session_edge_neighbors(runtime, node_id, neighbors)
    neighbors = merge_derived_fact_neighbors(
        ctx.knowledge,
        ctx.workspace.id,
        node_id,
        neighbors,
    )
    return {
        "node_id": node_id,
        "depth": min(max(1, depth), 5),
        "neighbors": neighbors,
    }


def op_paths(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    source = str(args.get("source", "")).strip()
    target = str(args.get("target", "")).strip()
    if not source or not target:
        return {"error": "source and target are required"}
    algorithm = str(args.get("algorithm", "bfs"))
    directed = bool(args.get("directed", True))
    if algorithm not in {"bfs", "dijkstra"}:
        algorithm = "bfs"
    return find_path(
        ctx.graph_runtime(),
        source=source,
        target=target,
        algorithm=algorithm,
        directed=directed,
    )


# ── Semantica-compat & decision operations ──
"""Semantica MCP–aligned workspace tool handlers."""


import json
from typing import Any

from basis.services.kernel import WorkspaceCoreContext
from basis.services.graph.graph_access import (
    context_graph,
    persist_graph_session,
    require_graph_mutation,
)
from basis.services.graph.governance.decisions_read import get_causal_chain as basis_decision_chain
from basis.services.graph.governance.decisions_read import list_decisions
from basis.services.workspace import operations as workspace_ops
from basis.services.errors import AdminError
from basis.services.graph.reads.export_read import export_graph as export_graph_content
from basis.services.graph.reads.read import get_node
from basis.services.graph.session.guard import require_graph_session
from basis.services.kernel.evidence import (
    optional_evidence_attestation,
    optional_metadata_with_evidence,
    resolve_extract_text,
)
from basis.services.knowledge.services.graph_audit import audit_graph


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
    from basis.services.graph.reads.projection_visibility import count_projection_nodes

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
            payload = op_neighbors(
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
            payload = op_graph_search(
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
            return op_find_entities(ctx, {"query": query, "limit": limit})

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


# ── Reasoning operations ──
"""Reasoning application services."""


from typing import Any

from basis.services.kernel.evidence import optional_evidence_attestation
from basis.services.kernel import WorkspaceCoreContext
from basis.services.kernel import require_workspace_editor
from basis.services.errors import AdminError
from basis.services.knowledge.services.graph_audit import audit_graph
from basis.services.knowledge.services.derived_facts_service import persist_reasoning_derived
from basis.services.graph.reasoning.forward import proof_chains_for_run
from basis.services.graph.reasoning.run import run_reasoning
from basis.services.graph.session.guard import require_graph_session
from basis.services.knowledge.services.reasoning_ground_facts import ground_fact_strings_from_typed_facts


def op_list_reasoning_ground_facts(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(1, int(args.get("limit", 200))), 500)
    facts = ground_fact_strings_from_typed_facts(ctx.knowledge, ctx.workspace.id, limit=limit)
    return {"facts": facts}


def op_list_rules(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(1, int(args.get("limit", 100))), 200)
    rules = ctx.knowledge.list_reasoning_rules(ctx.workspace.id, limit=limit)
    return {"rules": rules}


def op_get_rule(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    rule_id = str(args.get("rule_id", "")).strip()
    if not rule_id:
        return {"error": "rule_id is required"}
    try:
        rule = ctx.knowledge.get_reasoning_rule(ctx.workspace.id, rule_id)
    except AdminError as exc:
        if exc.code == "not_found":
            return {"error": "rule not found"}
        raise
    return {"rule": rule}


def op_run_reasoning(ctx: WorkspaceCoreContext, args: dict[str, Any]) -> dict[str, Any]:
    attestation, evidence_err = optional_evidence_attestation(ctx, args)
    if evidence_err:
        return evidence_err

    facts = args.get("facts")
    rules = args.get("rules")
    if not isinstance(rules, list) or not rules:
        return {"error": "rules is required (non-empty array of rule strings)"}
    rules_s = [str(r) for r in rules]
    facts_limit = min(max(1, int(args.get("facts_limit", 200))), 500)
    facts_source = "request"
    if facts is None or (isinstance(facts, list) and len(facts) == 0):
        facts_s = ground_fact_strings_from_typed_facts(
            ctx.knowledge,
            ctx.workspace.id,
            limit=facts_limit,
        )
        facts_source = "typed_facts"
    elif isinstance(facts, list):
        facts_s = [str(f) for f in facts]
    else:
        return {"error": "facts must be an array of strings when provided"}
    if not facts_s:
        return {
            "error": "no ground facts: pass facts[] or materialize typed_facts in the workspace",
        }
    apply_to_graph = bool(args.get("apply_to_graph", False))
    mode = str(args.get("mode") or "forward")
    inferred_edge_type = args.get("inferred_edge_type")
    if (
        not apply_to_graph
        and facts_source == "request"
        and facts_s
        and rules_s
        and mode == "forward"
        and inferred_edge_type is None
    ):
        from semantica.reasoning import Reasoner

        reasoner = Reasoner()
        for rule in rules_s:
            reasoner.add_rule(rule)
        inferred = reasoner.infer_facts(facts_s)
        inferred_list = inferred if isinstance(inferred, list) else list(inferred)
        fast: dict[str, Any] = {
            "inferred_facts": inferred_list,
            "derived_facts": inferred_list,
            "facts_source": facts_source,
            "ground_facts": facts_s,
            "proof_chains": proof_chains_for_run(facts_s, rules_s, inferred_list),
        }
        if attestation:
            fast["evidence"] = attestation
        return fast

    if apply_to_graph:
        require_workspace_editor(ctx)
    else:
        ctx.store.get_workspace_for(ctx.user, ctx.workspace.id, "viewer")

    runtime = ctx.graph_runtime()
    session = require_graph_session(runtime)
    graph_evidence = attestation if apply_to_graph and attestation else None
    summary = run_reasoning(
        session,
        facts=facts_s,
        rules=rules_s,
        mode=mode,
        apply_to_graph=apply_to_graph,
        inferred_edge_type=inferred_edge_type,
        graph_evidence=graph_evidence,
    )
    if attestation and not apply_to_graph:
        summary["evidence"] = attestation
    summary["proof_chains"] = proof_chains_for_run(
        facts_s,
        rules_s,
        list(summary.get("inferred_facts") or []),
    )
    summary["facts_source"] = facts_source
    summary["ground_facts"] = facts_s
    if apply_to_graph and summary.get("mutated"):
        summary["derived_facts_persisted"] = persist_reasoning_derived(
            ctx.knowledge,
            ctx.workspace.id,
            list(summary.get("proof_chains") or []),
        )
        created = int(summary["derived_facts_persisted"].get("created") or 0)
        if created > 0:
            if ctx.rebuild_projection is None:
                return {"error": "graph projection rebuild is unavailable"}
            summary["projection"] = ctx.rebuild_projection()
        elif ctx.persist_graph is not None:
            ctx.persist_graph(ctx.workspace.id)
        audit_extra: dict[str, Any] = {
            "added_edges": summary.get("added_edges"),
            "rules_fired": summary.get("rules_fired"),
            "derived_facts_created": created,
            **(
                {"projection_revision": summary["projection"].get("projection_revision")}
                if isinstance(summary.get("projection"), dict)
                else {}
            ),
        }
        if attestation:
            audit_extra["chunk_id"] = attestation["chunk_id"]
        audit_graph(
            ctx.store,
            ctx.user,
            ctx.workspace.id,
            "workspace.graph.reasoning_apply",
            extra=audit_extra,
        )
    return summary
