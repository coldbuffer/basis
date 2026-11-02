"""RDF / SKOS parsing for workspace Explorer HTTP."""

from __future__ import annotations

import importlib.util
from typing import Any

import rdflib
from rdflib.namespace import RDF, SKOS

_HAS_DEFUSEDXML = importlib.util.find_spec("defusedxml") is not None


def safe_parse_rdf(g: rdflib.Graph, data: bytes, rdf_format: str) -> None:
    """Parse RDF bytes into *g*, guarding against XXE for XML-based formats."""
    xml_formats = {"xml", "rdf", "rdf/xml", "application/rdf+xml"}
    if rdf_format.lower() in xml_formats:
        if not _HAS_DEFUSEDXML:
            raise ImportError(
                "defusedxml is required to safely parse RDF/XML content but is "
                "not installed. Install it with: pip install defusedxml"
            )
        import defusedxml

        defusedxml.defuse_stdlib()
    g.parse(data=data, format=rdf_format)


def _get_best_label(graph: rdflib.Graph, subject: rdflib.URIRef, predicate: rdflib.URIRef) -> str:
    labels = list(graph.objects(subject, predicate))
    if not labels:
        return ""
    for lbl in labels:
        if getattr(lbl, "language", None) == "en":
            return str(lbl)
    for lbl in labels:
        lang = getattr(lbl, "language", "")
        if lang and lang.startswith("en"):
            return str(lbl)
    for lbl in labels:
        if getattr(lbl, "language", None) is None:
            return str(lbl)
    return str(labels[0])


def _get_all_labels(graph: rdflib.Graph, subject: rdflib.URIRef, predicate: rdflib.URIRef) -> list[str]:
    return list({str(lbl) for lbl in graph.objects(subject, predicate)})


def parse_skos_file(
    file_bytes: bytes, rdf_format: str = "turtle"
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse SKOS from RDF bytes into ContextGraph node/edge dicts."""
    g = rdflib.Graph()
    try:
        safe_parse_rdf(g, file_bytes, rdf_format)
    except Exception as exc:
        raise ValueError(
            f"Failed to parse RDF file as {rdf_format}. Ensure the file is valid. Details: {exc}"
        ) from exc

    nodes_dict: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    for scheme in g.subjects(RDF.type, SKOS.ConceptScheme):
        uri = str(scheme)
        pref_label = _get_best_label(g, scheme, SKOS.prefLabel)
        if not pref_label:
            pref_label = uri.split("/")[-1].split("#")[-1]
        nodes_dict[uri] = {
            "id": uri,
            "type": "skos:ConceptScheme",
            "properties": {
                "content": pref_label,
                "alt_labels": _get_all_labels(g, scheme, SKOS.altLabel),
                "description": _get_best_label(g, scheme, SKOS.definition),
            },
        }

    for concept in g.subjects(RDF.type, SKOS.Concept):
        uri = str(concept)
        pref_label = _get_best_label(g, concept, SKOS.prefLabel)
        if not pref_label:
            pref_label = uri.split("/")[-1].split("#")[-1]
        nodes_dict[uri] = {
            "id": uri,
            "type": "skos:Concept",
            "properties": {
                "content": pref_label,
                "alt_labels": _get_all_labels(g, concept, SKOS.altLabel),
                "description": _get_best_label(g, concept, SKOS.definition),
            },
        }

    structural_preds = {
        SKOS.broader: "skos:broader",
        SKOS.narrower: "skos:narrower",
        SKOS.inScheme: "skos:inScheme",
        SKOS.related: "skos:related",
        SKOS.topConceptOf: "skos:topConceptOf",
        SKOS.hasTopConcept: "skos:hasTopConcept",
    }

    for pred, edge_type in structural_preds.items():
        for source, target in g.subject_objects(pred):
            if str(source) in nodes_dict and str(target) in nodes_dict:
                edges.append(
                    {
                        "source_id": str(source),
                        "target_id": str(target),
                        "type": edge_type,
                        "weight": 1.0,
                        "properties": {},
                    }
                )

    return list(nodes_dict.values()), edges
