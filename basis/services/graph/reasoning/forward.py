"""Forward-chaining reasoner with proof chains (F-RUL-03) for workspace reasoning/run."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_FACT_RE = re.compile(r"^(?P<predicate>[A-Za-z_][\w:-]*)\((?P<args>.*)\)$")


def _parse_fact(fact: str) -> Optional[Tuple[str, List[str]]]:
    match = _FACT_RE.match((fact or "").strip())
    if not match:
        return None
    args = [arg.strip().strip('"').strip("'") for arg in match.group("args").split(",") if arg.strip()]
    return match.group("predicate"), args


def _parse_rule(rule: str) -> Optional[Tuple[List[Tuple[str, List[str]]], Tuple[str, List[str]]]]:
    cleaned = (rule or "").strip()
    if not cleaned.upper().startswith("IF ") or " THEN " not in cleaned.upper():
        return None
    upper = cleaned.upper()
    then_index = upper.index(" THEN ")
    antecedent_text = cleaned[3:then_index]
    consequent_text = cleaned[then_index + 6 :]
    antecedents = []
    for segment in re.split(r" AND ", " ".join(antecedent_text.split()), flags=re.IGNORECASE):
        parsed = _parse_fact(segment)
        if parsed is None:
            return None
        antecedents.append(parsed)
    consequent = _parse_fact(consequent_text)
    if consequent is None:
        return None
    return antecedents, consequent


def _token_is_variable(token: str) -> bool:
    return token.startswith("?")


def _match_pattern(
    pattern: Tuple[str, List[str]],
    fact: Tuple[str, List[str]],
    bindings: Dict[str, str],
) -> Optional[Dict[str, str]]:
    pattern_predicate, pattern_args = pattern
    fact_predicate, fact_args = fact
    if pattern_predicate != fact_predicate or len(pattern_args) != len(fact_args):
        return None

    next_bindings = dict(bindings)
    for pattern_arg, fact_arg in zip(pattern_args, fact_args):
        if _token_is_variable(pattern_arg):
            bound_value = next_bindings.get(pattern_arg)
            if bound_value is None:
                next_bindings[pattern_arg] = fact_arg
            elif bound_value != fact_arg:
                return None
        elif pattern_arg != fact_arg:
            return None
    return next_bindings


def _instantiate(pattern: Tuple[str, List[str]], bindings: Dict[str, str]) -> str:
    predicate, args = pattern
    resolved = [bindings.get(arg, arg) for arg in args]
    return f"{predicate}({', '.join(resolved)})"


@dataclass(frozen=True)
class ProofChain:
    conclusion: str
    rule: str
    premises: List[str]

    def as_dict(self) -> dict[str, object]:
        return {"conclusion": self.conclusion, "rule": self.rule, "premises": list(self.premises)}


def infer_with_proof_chains(facts: List[str], rules: List[str]) -> Tuple[List[str], List[ProofChain]]:
    """Mirror semantica fallback forward reasoner; record rule + premises per inference."""
    parsed_facts = [parsed for parsed in (_parse_fact(fact) for fact in facts) if parsed is not None]
    inferred: List[str] = []
    proofs: List[ProofChain] = []
    known = set(facts)

    for rule in rules:
        parsed_rule = _parse_rule(rule)
        if parsed_rule is None:
            continue
        antecedents, consequent = parsed_rule
        bindings_list: List[Dict[str, str]] = [{}]
        for antecedent in antecedents:
            next_bindings: List[Dict[str, str]] = []
            for bindings in bindings_list:
                for fact_tuple in parsed_facts:
                    matched = _match_pattern(antecedent, fact_tuple, bindings)
                    if matched is not None:
                        next_bindings.append(matched)
            bindings_list = next_bindings
            if not bindings_list:
                break
        for bindings in bindings_list:
            candidate = _instantiate(consequent, bindings)
            if candidate not in known:
                premises = [_instantiate(ant, bindings) for ant in antecedents]
                known.add(candidate)
                inferred.append(candidate)
                proofs.append(ProofChain(conclusion=candidate, rule=rule.strip(), premises=premises))
    return inferred, proofs


def proof_chains_for_run(facts: List[str], rules: List[str], inferred_facts: List[str]) -> List[dict[str, object]]:
    """Return proof steps aligned with inferred_facts from a reasoning run."""
    _, proofs = infer_with_proof_chains(facts, rules)
    by_conclusion = {p.conclusion: p for p in proofs}
    ordered: List[dict[str, object]] = []
    for fact in inferred_facts:
        step = by_conclusion.get(fact)
        if step is not None:
            ordered.append(step.as_dict())
        else:
            ordered.append({"conclusion": fact, "rule": "", "premises": []})
    return ordered
