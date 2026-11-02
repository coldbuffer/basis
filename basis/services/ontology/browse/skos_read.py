"""Hub SKOS reads (schemes, concept search, concept detail)."""

from __future__ import annotations

import logging
from typing import Any

from basis.services.ontology.hub.catalog import _CONCEPT_TYPES, _node_label
from basis.services.ontology.browse.preview_read import extract_namespace
from basis.services.errors import AdminError

logger = logging.getLogger(__name__)


def _engine_config(session: Any) -> dict[str, Any]:
    return {"store": session.graph.store if hasattr(session.graph, "store") else None}


def list_skos_schemes(session: Any) -> list[dict[str, Any]]:
    try:
        from semantica.ontology import OntologyEngine

        engine = OntologyEngine(**_engine_config(session))
        vocabularies = engine.list_vocabularies()

        all_nodes, _ = session.get_nodes(skip=0, limit=999_999)
        concept_counts: dict[str, int] = {}
        for node in all_nodes:
            scheme_uri = node.get("properties", {}).get("scheme_uri")
            if scheme_uri and node.get("type") in _CONCEPT_TYPES:
                concept_counts[scheme_uri] = concept_counts.get(scheme_uri, 0) + 1

        return [
            {
                "uri": vocab["uri"],
                "title": vocab["label"]
                or vocab["uri"].rsplit("/", 1)[-1].rsplit("#", 1)[-1],
                "description": None,
                "concept_count": concept_counts.get(vocab["uri"], 0),
            }
            for vocab in vocabularies
        ]
    except Exception as exc:
        logger.warning("OntologyEngine.list_vocabularies failed, falling back to session: %s", exc)
        nodes, _ = session.get_nodes(node_type="skos:ConceptScheme", skip=0, limit=999_999)
        all_edges, _ = session.get_edges(skip=0, limit=999_999)
        concept_counts: dict[str, int] = {}
        for edge in all_edges:
            if edge.get("type") in {"skos:inScheme", "skos:topConceptOf"}:
                concept_counts[edge["target"]] = concept_counts.get(edge["target"], 0) + 1
            elif edge.get("type") == "skos:hasTopConcept":
                concept_counts[edge["source"]] = concept_counts.get(edge["source"], 0) + 1

        result = []
        for node in nodes:
            props = node.get("properties", {})
            nid = node.get("id", "")
            result.append(
                {
                    "uri": nid,
                    "title": _node_label(node),
                    "description": props.get("description") or props.get("skos:definition"),
                    "concept_count": concept_counts.get(nid, 0),
                }
            )
        return result


def search_skos_concepts(
    session: Any,
    *,
    query: str,
    scheme_uri: str | None = None,
) -> list[dict[str, Any]]:
    try:
        from semantica.ontology import OntologyEngine

        engine = OntologyEngine(**_engine_config(session))
        concepts = engine.search_concepts(query, scheme_uri=scheme_uri)
        return [
            {
                "uri": concept["uri"],
                "label": concept["label"],
                "type": "skos:Concept",
                "entity_type": "concept",
                "definition": None,
                "source_ontology": scheme_uri,
                "namespace_prefix": extract_namespace(concept["uri"]),
            }
            for concept in concepts
        ]
    except Exception as exc:
        logger.warning("OntologyEngine.search_concepts failed, using fallback: %s", exc)
        raw_hits = session.search(query, 300)
        results: list[dict[str, Any]] = []

        for hit in raw_hits:
            node = hit.get("node", hit)
            ntype = node.get("type", "")
            if ntype not in _CONCEPT_TYPES:
                continue
            if scheme_uri:
                scheme = node.get("properties", {}).get("scheme_uri")
                if scheme != scheme_uri:
                    continue

            label = _node_label(node)
            props = node.get("properties", {})
            definition = (
                props.get("rdfs:comment")
                or props.get("skos:definition")
                or props.get("description")
            )

            results.append(
                {
                    "uri": node.get("id", ""),
                    "label": label,
                    "type": ntype,
                    "entity_type": "concept",
                    "definition": definition,
                    "source_ontology": props.get("scheme_uri"),
                    "namespace_prefix": extract_namespace(node.get("id", "")),
                }
            )
            if len(results) >= 50:
                break

        return results


def _concept_detail_from_session(session: Any, concept_uri: str, node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties", {})
    out_edges, _ = session.get_edges(source=concept_uri, skip=0, limit=9999)
    in_edges, _ = session.get_edges(target=concept_uri, skip=0, limit=9999)

    def collect_out(rel: str) -> list[str]:
        return [e["target"] for e in out_edges if e.get("type") == rel]

    def collect_in(rel: str) -> list[str]:
        return [e["source"] for e in in_edges if e.get("type") == rel]

    pref_label = props.get("pref_label") or props.get("skos:prefLabel") or _node_label(node)
    alt_labels = props.get("alt_labels") or props.get("skos:altLabel") or []
    if isinstance(alt_labels, str):
        alt_labels = [alt_labels]
    hidden_labels = props.get("skos:hiddenLabel") or []
    if isinstance(hidden_labels, str):
        hidden_labels = [hidden_labels]

    scheme_uri = props.get("scheme_uri")
    if not scheme_uri:
        candidates = collect_out("skos:inScheme") or collect_out("skos:topConceptOf")
        scheme_uri = candidates[0] if candidates else None

    return {
        "uri": concept_uri,
        "pref_label": pref_label,
        "alt_labels": list(alt_labels),
        "hidden_labels": list(hidden_labels),
        "definition": props.get("definition") or props.get("skos:definition"),
        "scope_note": props.get("skos:scopeNote"),
        "editorial_note": props.get("skos:editorialNote"),
        "broader": collect_out("skos:broader") + collect_in("skos:narrower"),
        "narrower": collect_out("skos:narrower") + collect_in("skos:broader"),
        "related": collect_out("skos:related"),
        "exact_match": collect_out("skos:exactMatch"),
        "close_match": collect_out("skos:closeMatch"),
        "broad_match": collect_out("skos:broadMatch"),
        "narrow_match": collect_out("skos:narrowMatch"),
        "scheme_uri": scheme_uri,
    }


def get_skos_concept(session: Any, concept_uri: str) -> dict[str, Any]:
    try:
        from semantica.ontology import OntologyEngine

        node = session.get_node(concept_uri)
        if node is None:
            raise AdminError(404, "not_found", "Concept not found.")

        scheme_uri = node.get("properties", {}).get("scheme_uri")
        if scheme_uri:
            engine = OntologyEngine(**_engine_config(session))
            concepts = engine.list_concepts(scheme_uri)
            concept_data = next((c for c in concepts if c["uri"] == concept_uri), None)
            if concept_data:
                return {
                    "uri": concept_data["uri"],
                    "pref_label": concept_data["pref_label"],
                    "alt_labels": concept_data.get("alt_labels", []),
                    "hidden_labels": [],
                    "definition": None,
                    "scope_note": None,
                    "editorial_note": None,
                    "broader": [],
                    "narrower": [],
                    "related": [],
                    "exact_match": [],
                    "close_match": [],
                    "broad_match": [],
                    "narrow_match": [],
                    "scheme_uri": scheme_uri,
                }

        return _concept_detail_from_session(session, concept_uri, node)
    except AdminError:
        raise
    except Exception as exc:
        logger.warning("OntologyEngine SKOS methods failed, using fallback: %s", exc)
        node = session.get_node(concept_uri)
        if node is None:
            raise AdminError(404, "not_found", "Concept not found.")
        return _concept_detail_from_session(session, concept_uri, node)
