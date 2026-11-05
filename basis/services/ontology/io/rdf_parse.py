"""RDF / SKOS parsing for workspace Explorer HTTP."""

from __future__ import annotations

import importlib.util
import re
from typing import Any

import rdflib
from rdflib.namespace import RDF, SKOS

_HAS_DEFUSEDXML = importlib.util.find_spec("defusedxml") is not None

# FIBO-style RDF/XML declares namespace prefixes as internal DTD entities
# (`<!ENTITY xsd "http://www.w3.org/2001/XMLSchema#">`). defusedxml rejects every
# entity declaration, so those literals are expanded and the DOCTYPE removed
# before parse. External, parameter, and nested entities are left untouched.
_MAX_INTERNAL_ENTITIES = 512
_MAX_ENTITY_VALUE_CHARS = 4096
_MAX_EXPANSION_GROWTH_BYTES = 1_000_000
_ENTITY_NAME = r"[A-Za-z_:][A-Za-z0-9._:-]*"
_LITERAL_ENTITY_RE = re.compile(
    rf"""<!ENTITY\s+({_ENTITY_NAME})\s+(?:"([^"]*)"|'([^']*)')\s*>"""
)
_UNSAFE_ENTITY_RE = re.compile(
    rf"""<!ENTITY\s+(?:%\s*)?{_ENTITY_NAME}\s+(?:SYSTEM|PUBLIC)\b|<!ENTITY\s+%"""
)
_UNSAFE_VALUE_CHARS = set("<>&\"'")


def expand_literal_internal_entities(data: bytes) -> bytes:
    """Replace internal literal DTD entities and drop that DOCTYPE.

    Returns *data* unchanged when the document has no internal subset, or when
    any declaration is external, a parameter entity, nested, or otherwise unsafe.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data

    found = _internal_doctype_subset(text)
    if found is None:
        return data
    start, end, subset = found
    entities = _literal_entities(subset)
    if entities is None:
        return data

    body = text[:start] + text[end:]
    if entities:
        pattern = re.compile(
            "&(" + "|".join(re.escape(name) for name in sorted(entities, key=len, reverse=True)) + ");"
        )
        body = pattern.sub(lambda match: entities[match.group(1)], body)
    rewritten = body.encode("utf-8")
    if len(rewritten) > len(data) + _MAX_EXPANSION_GROWTH_BYTES:
        raise ValueError("RDF/XML internal entity expansion exceeds size limit")
    return rewritten


def _internal_doctype_subset(text: str) -> tuple[int, int, str] | None:
    start = text.find("<!DOCTYPE")
    if start < 0:
        return None
    index = start + len("<!DOCTYPE")
    limit = len(text)
    quote: str | None = None
    while index < limit:
        char = text[index]
        if quote:
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char == "[":
            subset_start = index + 1
            subset_quote: str | None = None
            cursor = subset_start
            while cursor < limit:
                current = text[cursor]
                if subset_quote:
                    if current == subset_quote:
                        subset_quote = None
                    cursor += 1
                    continue
                if current in {"'", '"'}:
                    subset_quote = current
                    cursor += 1
                    continue
                if text.startswith("]>", cursor):
                    return start, cursor + 2, text[subset_start:cursor]
                cursor += 1
            return None
        if char == ">":
            return None
        index += 1
    return None


def _literal_entities(subset: str) -> dict[str, str] | None:
    cleaned = re.sub(r"<!--.*?-->", "", subset, flags=re.DOTALL)
    if _UNSAFE_ENTITY_RE.search(cleaned):
        return None
    entities: dict[str, str] = {}
    for match in _LITERAL_ENTITY_RE.finditer(cleaned):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        if value is None or len(value) > _MAX_ENTITY_VALUE_CHARS or _UNSAFE_VALUE_CHARS.intersection(value):
            return None
        entities[match.group(1)] = value
        if len(entities) > _MAX_INTERNAL_ENTITIES:
            return None
    if len(re.findall(r"<!ENTITY\b", cleaned)) != len(entities):
        return None
    return entities


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
        data = expand_literal_internal_entities(data)
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
