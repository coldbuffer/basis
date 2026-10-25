"""Workspace reasoning run (Semantica Reasoner + optional graph apply)."""

from __future__ import annotations

from typing import Any

from basis.domain.graph.reasoning.forward import _parse_fact, infer_with_proof_chains


def _apply_inferred_edges(
    session: Any,
    inferred_facts: list[str],
    *,
    mode: str,
    rules: list[str],
    inferred_edge_type: str | None,
    graph_evidence: dict[str, Any] | None = None,
) -> int:
    added_edges = 0
    for fact in inferred_facts:
        parsed = _parse_fact(fact)
        if parsed is None:
            continue
        predicate, args = parsed
        if len(args) != 2:
            continue
        source, target = args
        if session.get_node(source) is None:
            session.add_node(source, "entity", content=source)
        if session.get_node(target) is None:
            session.add_node(target, "entity", content=target)
        edge_type = inferred_edge_type or predicate
        edge_props: dict[str, Any] = {
            "inferred": True,
            "inferred_from": fact,
            "reasoning_mode": mode,
            "rules": list(rules),
        }
        if graph_evidence:
            edge_props["basis_evidence"] = dict(graph_evidence)
        session.add_edge(source, target, edge_type=edge_type, **edge_props)
        added_edges += 1
    return added_edges


def _infer_facts(facts: list[str], rules: list[str]) -> list[str]:
    inferred_facts: list[str] = []
    try:
        from semantica.reasoning.reasoner import Reasoner

        reasoner = Reasoner()
        inferred = reasoner.infer_facts(facts, rules)
        if isinstance(inferred, list):
            inferred_facts = inferred
    except ImportError:
        pass
    except Exception:
        pass
    if not inferred_facts:
        inferred_facts, _proofs = infer_with_proof_chains(facts, rules)
    return inferred_facts


def run_reasoning(
    session: Any,
    *,
    facts: list[str],
    rules: list[str],
    mode: str = "forward",
    apply_to_graph: bool = False,
    inferred_edge_type: str | None = None,
    graph_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inferred_facts = _infer_facts(list(facts), list(rules))
    added_edges = 0
    if apply_to_graph and inferred_facts:
        added_edges = _apply_inferred_edges(
            session,
            inferred_facts,
            mode=mode,
            rules=list(rules),
            inferred_edge_type=inferred_edge_type,
            graph_evidence=graph_evidence,
        )
    payload: dict[str, Any] = {
        "inferred_facts": inferred_facts,
        "rules_fired": len(inferred_facts),
        "added_edges": added_edges,
        "mutated": added_edges > 0,
    }
    if graph_evidence:
        payload["evidence"] = dict(graph_evidence)
    return payload
