"""Serialize ontology subgraph nodes/edges to Turtle for SHACL validation."""

from __future__ import annotations

import asyncio
from typing import Any

from basis.services.ontology.hub.catalog import (
    _classify_node_type,
    _node_belongs_to_ontology,
    resolve_registry_entry,
)
from basis.services.errors import AdminError


def _ontology_namespace(uri: str) -> str:
    if "#" in uri:
        return uri.rsplit("#", 1)[0] + "#"
    if uri.endswith("/"):
        return uri
    return uri.rstrip("#/") + "#"


def _as_uri_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if item is None or item == "":
                continue
            if isinstance(item, dict):
                uri = item.get("uri") or item.get("id") or item.get("@id")
                if uri:
                    result.append(str(uri))
            else:
                result.append(str(item))
        return result
    if isinstance(value, dict):
        uri = value.get("uri") or value.get("id") or value.get("@id")
        return [str(uri)] if uri else []
    return [str(value)]


def _data_graph_entities(
    nodes: list[dict[str, Any]],
    ontology_uri: str | None = None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in nodes:
        if _classify_node_type(node.get("type", "")) not in {
            "class",
            "property",
            "individual",
            "concept",
            "scheme",
        }:
            continue
        if ontology_uri and not _node_belongs_to_ontology(node, ontology_uri):
            continue
        result.append(node)
    return result


async def data_graph_turtle_for_uri(
    registry: dict[str, Any],
    session: Any,
    uri: str,
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> str:
    resolve_registry_entry(registry, session, uri)

    try:
        import rdflib
    except ImportError as exc:
        raise ImportError("rdflib is not installed.") from exc

    entities = _data_graph_entities(nodes, uri)
    base_namespace = _ontology_namespace(uri)

    g = rdflib.Graph()
    OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
    RDF = rdflib.RDF
    RDFS = rdflib.RDFS
    SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
    DCT = rdflib.Namespace("http://purl.org/dc/terms/")
    DC = rdflib.Namespace("http://purl.org/dc/elements/1.1/")
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    XSD = rdflib.XSD
    ONTO = rdflib.Namespace(base_namespace)

    g.bind("owl", OWL)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("skos", SKOS)
    g.bind("dct", DCT)
    g.bind("dc", DC)
    g.bind("sh", SH)
    g.bind("xsd", XSD)
    g.bind("onto", ONTO)

    def _resolve_uri(val: str, base_ns: str) -> rdflib.URIRef:
        val_str = str(val).strip()
        if val_str == "a":
            return rdflib.RDF.type
        if val_str.startswith(("http://", "https://", "urn:", "ftp://")):
            return rdflib.URIRef(val_str)
        prefix_map = {
            "owl": "http://www.w3.org/2002/07/owl#",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "skos": "http://www.w3.org/2004/02/skos/core#",
            "dct": "http://purl.org/dc/terms/",
            "dc": "http://purl.org/dc/elements/1.1/",
            "sh": "http://www.w3.org/ns/shacl#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "onto": base_ns,
        }
        if ":" in val_str and not val_str.startswith("/"):
            prefix, _, rest = val_str.partition(":")
            if prefix in prefix_map:
                return rdflib.URIRef(prefix_map[prefix] + rest)
            return rdflib.URIRef(val_str)
        if val_str.startswith("#"):
            val_str = val_str.lstrip("#")
        if base_ns.endswith(("/", "#")):
            return rdflib.URIRef(base_ns + val_str.lstrip("/"))
        return rdflib.URIRef(base_ns + "#" + val_str.lstrip("/"))

    _shorthand_types = {
        "class": "owl:Class",
        "object_property": "owl:ObjectProperty",
        "datatype_property": "owl:DatatypeProperty",
        "annotation_property": "owl:AnnotationProperty",
        "property": "rdf:Property",
        "individual": "owl:NamedIndividual",
        "concept": "skos:Concept",
        "scheme": "skos:ConceptScheme",
        "ontology": "owl:Ontology",
    }
    _uri_predicates = {
        "rdf:type",
        "a",
        "rdfs:subClassOf",
        "rdfs:domain",
        "rdfs:range",
        "owl:equivalentClass",
        "owl:equivalentProperty",
        "owl:sameAs",
        "skos:exactMatch",
        "skos:closeMatch",
        "skos:broadMatch",
        "skos:narrowMatch",
        "skos:relatedMatch",
        "sh:targetClass",
        "sh:targetNode",
    }
    _literal_predicates = {
        "rdfs:label",
        "rdfs:comment",
        "skos:definition",
        "skos:prefLabel",
        "skos:altLabel",
        "dct:description",
        "dct:title",
        "dc:title",
        "dc:description",
        "version",
    }
    _skip_keys = {
        "id",
        "type",
        "content",
        "valid_from",
        "valid_until",
        "scheme_uri",
        "ontology_uri",
        "ontology",
    }

    entity_ids: set[str] = set()
    for node in entities:
        nid_str = str(node.get("id", "")).strip()
        if not nid_str:
            continue
        entity_ids.add(nid_str)
        subj = _resolve_uri(nid_str, base_namespace)

        node_type = node.get("type", "")
        if node_type:
            for t in _as_uri_list(node_type):
                t_mapped = _shorthand_types.get(str(t).lower(), str(t))
                g.add((subj, rdflib.RDF.type, _resolve_uri(t_mapped, base_namespace)))

        content = str(node.get("content", "")).strip()
        props = node.get("properties", {}) or {}
        if content and "rdfs:label" not in props and "pref_label" not in props and "label" not in props:
            g.add((subj, RDFS.label, rdflib.Literal(content)))

        for key, val in props.items():
            if key in _skip_keys or val is None or val == "":
                continue
            pred = _resolve_uri(str(key), base_namespace)
            values = _as_uri_list(val) if isinstance(val, (list, dict)) else [val]
            for item in values:
                if item is None or item == "":
                    continue
                if isinstance(item, dict):
                    item = item.get("uri") or item.get("id") or item.get("@id")
                    if not item:
                        continue
                if str(key) in _uri_predicates or (
                    str(key) not in _literal_predicates
                    and str(item).strip().startswith(("http://", "https://", "urn:"))
                ):
                    g.add((subj, pred, _resolve_uri(str(item), base_namespace)))
                else:
                    g.add((subj, pred, rdflib.Literal(str(item))))

    for edge in edges:
        source = str(edge.get("source", edge.get("source_id", ""))).strip()
        target = str(edge.get("target", edge.get("target_id", ""))).strip()
        pred_str = str(edge.get("type", "related_to")).strip()
        if not source or not target:
            continue
        if source in entity_ids or target in entity_ids:
            g.add(
                (
                    _resolve_uri(source, base_namespace),
                    _resolve_uri(pred_str, base_namespace),
                    _resolve_uri(target, base_namespace),
                )
            )

    return await asyncio.to_thread(g.serialize, format="turtle")
