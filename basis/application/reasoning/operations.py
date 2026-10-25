"""Reasoning application services."""

from __future__ import annotations

from typing import Any

from basis.application.evidence import optional_evidence_attestation
from basis.application.kernel import WorkspaceCoreContext
from basis.application.kernel import require_workspace_editor
from basis.domain.errors import AdminError
from basis.domain.knowledge.services.graph_audit import audit_graph
from basis.domain.knowledge.services.derived_facts_service import persist_reasoning_derived
from basis.domain.graph.reasoning.forward import proof_chains_for_run
from basis.domain.graph.reasoning.run import run_reasoning
from basis.domain.graph.session.guard import require_graph_session
from basis.domain.knowledge.reasoning_ground_facts import ground_fact_strings_from_typed_facts


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
