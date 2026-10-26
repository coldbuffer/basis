"""OWL 2 class restriction kinds supported by the ontology editor draft apply path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PropertyScope = Literal["object", "data"]
FillerRole = Literal["class", "individual", "datatype", "literal", "none"]
CardinalityMode = Literal["none", "qualified", "unqualified"]


@dataclass(frozen=True)
class RestrictionKindSpec:
    """How a draft restriction row maps to ``owl:Restriction`` node properties and edges."""

    owl_predicate: str
    filler_role: FillerRole
    cardinality_mode: CardinalityMode
    filler_edge_type: str | None


def restriction_spec(property_scope: str, restriction_type: str) -> RestrictionKindSpec | None:
    scope = (property_scope or "object").strip().lower()
    if scope not in ("object", "data"):
        scope = "object"
    key = (scope, restriction_type.strip())
    return _SPECS.get(key)


_SPECS: dict[tuple[str, str], RestrictionKindSpec] = {}

for _scope, _type, _pred, _filler, _card, _edge in (
    ("object", "someValuesFrom", "owl:someValuesFrom", "class", "none", "owl:someValuesFrom"),
    ("object", "allValuesFrom", "owl:allValuesFrom", "class", "none", "owl:allValuesFrom"),
    ("object", "hasValue", "owl:hasValue", "individual", "none", "owl:hasValue"),
    (
        "object",
        "minQualifiedCardinality",
        "owl:minQualifiedCardinality",
        "class",
        "qualified",
        "owl:onClass",
    ),
    (
        "object",
        "maxQualifiedCardinality",
        "owl:maxQualifiedCardinality",
        "class",
        "qualified",
        "owl:onClass",
    ),
    (
        "object",
        "qualifiedCardinality",
        "owl:qualifiedCardinality",
        "class",
        "qualified",
        "owl:onClass",
    ),
    ("object", "minCardinality", "owl:minCardinality", "none", "unqualified", None),
    ("object", "maxCardinality", "owl:maxCardinality", "none", "unqualified", None),
    ("object", "cardinality", "owl:cardinality", "none", "unqualified", None),
    ("data", "someValuesFrom", "owl:someValuesFrom", "datatype", "none", "owl:someValuesFrom"),
    ("data", "allValuesFrom", "owl:allValuesFrom", "datatype", "none", "owl:allValuesFrom"),
    ("data", "hasValue", "owl:hasValue", "literal", "none", None),
    (
        "data",
        "minQualifiedCardinality",
        "owl:minQualifiedCardinality",
        "datatype",
        "qualified",
        "owl:onDataRange",
    ),
    (
        "data",
        "maxQualifiedCardinality",
        "owl:maxQualifiedCardinality",
        "datatype",
        "qualified",
        "owl:onDataRange",
    ),
    (
        "data",
        "qualifiedCardinality",
        "owl:qualifiedCardinality",
        "datatype",
        "qualified",
        "owl:onDataRange",
    ),
    ("data", "minCardinality", "owl:minCardinality", "none", "unqualified", None),
    ("data", "maxCardinality", "owl:maxCardinality", "none", "unqualified", None),
    ("data", "cardinality", "owl:cardinality", "none", "unqualified", None),
):
    _SPECS[(_scope, _type)] = RestrictionKindSpec(
        owl_predicate=_pred,
        filler_role=_filler,
        cardinality_mode=_card,
        filler_edge_type=_edge,
    )


def supported_restriction_type_keys() -> frozenset[tuple[str, str]]:
    return frozenset(_SPECS.keys())
