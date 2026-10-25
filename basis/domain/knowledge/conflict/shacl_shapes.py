"""SHACL shapes for mapped functional properties (per-subject maxCount 1)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from basis.domain.knowledge.conflict.turtle import entity_node_iri


def per_subject_functional_shapes_turtle(
    assertions: list[dict[str, Any]],
    functional_predicate_iris: set[str],
) -> str:
    """NodeShapes targeting each subject node with maxCount 1 on functional predicates."""
    by_subject: dict[str, set[str]] = defaultdict(set)
    for item in assertions:
        pred = str(item.get("predicate_iri") or "").strip()
        subject_id = str(item.get("subject_id") or "").strip()
        if not pred or not subject_id or pred not in functional_predicate_iris:
            continue
        by_subject[subject_id].add(pred)

    if not by_subject:
        return ""

    lines = [
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        "@prefix basis: <urn:basis:shapes#> .",
        "",
    ]
    for index, (subject_id, predicates) in enumerate(sorted(by_subject.items()), start=1):
        shape_id = f"basis:SubjectFunctionalShape{index}"
        lines.append(f"{shape_id} a sh:NodeShape ;")
        lines.append(f"  sh:targetNode <{entity_node_iri(subject_id)}> ;")
        sorted_preds = sorted(predicates)
        for pred_index, predicate_iri in enumerate(sorted_preds):
            terminal = " ." if pred_index == len(sorted_preds) - 1 else " ;"
            lines.append("  sh:property [")
            lines.append(f"    sh:path <{predicate_iri}> ;")
            lines.append(f"    sh:maxCount 1")
            lines.append(f"  ]{terminal}")
        lines.append("")
    return "\n".join(lines)
