"""Ontology registry and alignment catalog."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Literal

from basis.domain.errors import AdminError

logger = logging.getLogger(__name__)

_MAX_ANALYSIS_NODES = 5_000
_MAX_ENTITIES_PER_SIDE = 500

_CLASS_TYPES = frozenset({
    "owl:Class", "rdfs:Class",
    "http://www.w3.org/2002/07/owl#Class",
    "http://www.w3.org/2000/01/rdf-schema#Class",
})
_PROPERTY_TYPES = frozenset({
    "owl:ObjectProperty", "owl:DatatypeProperty", "owl:AnnotationProperty",
    "rdfs:Property",
    "http://www.w3.org/2002/07/owl#ObjectProperty",
    "http://www.w3.org/2002/07/owl#DatatypeProperty",
    "http://www.w3.org/2002/07/owl#AnnotationProperty",
})
_INDIVIDUAL_TYPES = frozenset({
    "owl:NamedIndividual",
    "http://www.w3.org/2002/07/owl#NamedIndividual",
})
_CONCEPT_TYPES = frozenset({
    "skos:Concept",
    "http://www.w3.org/2004/02/skos/core#Concept",
})
_SCHEME_TYPES = frozenset({
    "skos:ConceptScheme",
    "http://www.w3.org/2004/02/skos/core#ConceptScheme",
})
_ONTOLOGY_TYPES = frozenset({
    "owl:Ontology",
    "http://www.w3.org/2002/07/owl#Ontology",
}) | _SCHEME_TYPES

_URI_PREFIX_MAP: dict[str, str] = {
    "http://www.w3.org/2002/07/owl#": "owl:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2004/02/skos/core#": "skos:",
    "http://purl.org/dc/terms/": "dcterms:",
    "http://purl.org/dc/elements/1.1/": "dc:",
    "http://schema.org/": "schema:",
    "http://www.w3.org/ns/shacl#": "sh:",
}

_ALIGNMENT_RELATIONS: dict[str, str] = {
    "owl:equivalentClass": "http://www.w3.org/2002/07/owl#equivalentClass",
    "owl:equivalentProperty": "http://www.w3.org/2002/07/owl#equivalentProperty",
    "skos:exactMatch": "http://www.w3.org/2004/02/skos/core#exactMatch",
    "skos:closeMatch": "http://www.w3.org/2004/02/skos/core#closeMatch",
    "skos:broadMatch": "http://www.w3.org/2004/02/skos/core#broadMatch",
    "skos:narrowMatch": "http://www.w3.org/2004/02/skos/core#narrowMatch",
    "skos:relatedMatch": "http://www.w3.org/2004/02/skos/core#relatedMatch",
}

AlignmentRelation = Literal[
    "owl:equivalentClass",
    "owl:equivalentProperty",
    "skos:exactMatch",
    "skos:closeMatch",
    "skos:broadMatch",
    "skos:narrowMatch",
    "skos:relatedMatch",
]


def uri_to_prefixed(uri: str) -> str:
    for base, prefix in _URI_PREFIX_MAP.items():
        if uri.startswith(base):
            return prefix + uri[len(base) :]
    return uri


def _local_name_from_uri(uri: str) -> str:
    text = str(uri or "").strip()
    if not text:
        return text
    trimmed = text.rstrip("/#")
    if "#" in trimmed:
        local = trimmed.rsplit("#", 1)[-1]
        if local:
            return local
    if "/" in trimmed:
        local = trimmed.rsplit("/", 1)[-1]
        if local:
            return local
    return trimmed or text


def _looks_like_iri(value: str) -> bool:
    probe = value.strip().lower()
    return probe.startswith(("http://", "https://", "urn:"))


def _humanize_rdf_label(candidate: Any, resource_uri: str) -> str:
    text = str(candidate or "").strip()
    if not text:
        return _local_name_from_uri(resource_uri)
    if any(ch.isspace() for ch in text):
        return text
    if _looks_like_iri(text):
        return _local_name_from_uri(text)
    return text


def _classify_node_type(node_type: str) -> str:
    if node_type in _CLASS_TYPES:
        return "class"
    if node_type in _PROPERTY_TYPES:
        return "property"
    if node_type in _INDIVIDUAL_TYPES:
        return "individual"
    if node_type in _CONCEPT_TYPES:
        return "concept"
    if node_type in _SCHEME_TYPES:
        return "scheme"
    if node_type in _ONTOLOGY_TYPES:
        return "ontology"
    return "unknown"


def _node_label(node: dict[str, Any]) -> str:
    props = node.get("properties", {})
    node_id = str(node.get("id", ""))
    for raw in (
        props.get("pref_label"),
        props.get("rdfs:label"),
        props.get("skos:prefLabel"),
        props.get("label"),
        props.get("content"),
        node.get("content"),
    ):
        if raw:
            label = _humanize_rdf_label(raw, node_id)
            if label:
                return label
    return _local_name_from_uri(node_id) if node_id else ""


def _alignment_id(source_uri: str, relation: str, target_uri: str) -> str:
    key = f"{source_uri}|{relation}|{target_uri}"
    return str(uuid.uuid5(uuid.NAMESPACE_OID, key))


def _label_from_uri(uri: str) -> str:
    fragment = uri.rsplit("#", 1)[-1] if "#" in uri else uri.rsplit("/", 1)[-1]
    return fragment or uri


def _node_source_ontology(node: dict[str, Any]) -> str | None:
    props = node.get("properties", {})
    return (
        props.get("scheme_uri")
        or props.get("source_ontology")
        or props.get("ontology_uri")
        or props.get("ontology")
    )


def published_entity_uris_for_ontology(
    versions: dict[str, Any] | None,
    ontology_uri: str,
) -> set[str]:
    """Entity IRIs recorded in published version diffs (editor may use urn: vs https:)."""
    if not versions:
        return set()
    uris: set[str] = set()
    for entry in versions.get(ontology_uri) or []:
        diff = _entry_field(entry, "diff_summary") or {}
        if not isinstance(diff, dict):
            continue
        for key in (
            "added_classes",
            "added_properties",
            "added_individuals",
            "added_concepts",
        ):
            uris.update(str(u).strip() for u in (diff.get(key) or []) if str(u).strip())
    return uris


def _node_belongs_to_ontology(
    node: dict[str, Any],
    ontology_uri: str,
    known_ontology_uris: set[str] | None = None,
    *,
    published_entity_uris: set[str] | None = None,
) -> bool:
    nid = node.get("id", "")
    if published_entity_uris and nid in published_entity_uris:
        return True
    if nid == ontology_uri:
        return True
    owner = _node_source_ontology(node)
    if owner:
        return owner == ontology_uri
    if known_ontology_uris:
        namespace_owners = [
            candidate
            for candidate in known_ontology_uris
            if nid == candidate
            or nid.startswith(
                (candidate.rstrip("#/") + "#", candidate.rstrip("#/") + "/")
            )
        ]
        if namespace_owners and max(namespace_owners, key=len) != ontology_uri:
            return False
    stem = ontology_uri.rstrip("#/")
    if not nid.startswith((stem + "#", stem + "/")):
        return False
    local_name = nid[len(stem) + 1 :]
    return "#" not in local_name and "/" not in local_name


def _is_ontology_entity(node: dict[str, Any]) -> bool:
    return _classify_node_type(node.get("type", "")) in {"class", "property", "concept", "scheme"}


def _ontology_entities(nodes: list[dict[str, Any]], ontology_uri: str | None = None) -> list[dict[str, Any]]:
    result = []
    for node in nodes:
        if not _is_ontology_entity(node):
            continue
        if ontology_uri and not _node_belongs_to_ontology(node, ontology_uri):
            continue
        result.append(node)
    return result


def _label_similarity(left: str, right: str) -> float:
    left_norm = " ".join(left.lower().replace("_", " ").replace("-", " ").split())
    right_norm = " ".join(right.lower().replace("_", " ").replace("-", " ").split())
    if not left_norm or not right_norm:
        return 0.0
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    token_score = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return round(max(sequence, token_score), 4)


def _token_set(label: str) -> frozenset[str]:
    return frozenset(label.lower().replace("_", " ").replace("-", " ").split())


def _tfidf_embedding_vectors(labels: list[str]) -> dict[str, list[float]] | None:
    if len(labels) < 2:
        return None
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        normed = [" ".join(l.lower().replace("_", " ").replace("-", " ").split()) for l in labels]
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        matrix = vec.fit_transform(normed)
        return {label: matrix[i].toarray().flatten().tolist() for i, label in enumerate(labels)}
    except Exception:
        return None


def _cosine_sim(v1: list[float], v2: list[float]) -> float:
    try:
        from semantica.kg import SimilarityCalculator

        return float(SimilarityCalculator().cosine_similarity(v1, v2))
    except Exception:
        import math

        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(b * b for b in v2))
        return dot / (n1 * n2) if n1 and n2 else 0.0


def _candidate_relation(source: dict[str, Any], target: dict[str, Any]) -> AlignmentRelation:
    source_type = _classify_node_type(source.get("type", ""))
    target_type = _classify_node_type(target.get("type", ""))
    if source_type == "class" and target_type == "class":
        return "owl:equivalentClass"
    if source_type == "property" and target_type == "property":
        return "owl:equivalentProperty"
    if source_type == "concept" and target_type == "concept":
        return "skos:exactMatch"
    return "skos:closeMatch"


def _entry_field(entry: Any, name: str, default: Any = None) -> Any:
    if hasattr(entry, name):
        return getattr(entry, name)
    if isinstance(entry, dict):
        return entry.get(name, default)
    return default


def _dump_entry(entry: Any, **updates: Any) -> dict[str, Any]:
    if hasattr(entry, "model_copy"):
        return entry.model_copy(update=updates).model_dump()
    if hasattr(entry, "model_dump"):
        data = entry.model_dump()
    elif isinstance(entry, dict):
        data = dict(entry)
    else:
        data = {}
    data.update(updates)
    return data


def resolve_registry_entry(
    registry: dict[str, Any],
    session: Any,
    uri: str,
) -> dict[str, Any]:
    """Return registry row for ``uri``, including implicit owl:Ontology nodes in the graph."""
    from basis.domain.ontology.browse.graph_scope import known_ontology_uris

    known = known_ontology_uris(session, registry)
    if uri not in known:
        raise AdminError(404, "not_found", "Ontology not found in registry.")

    entry = registry.get(uri)
    if entry is not None:
        if isinstance(entry, dict):
            return entry
        return _dump_entry(entry)

    node = session.get_node(uri)
    props = node.get("properties", {}) if node else {}
    name = _node_label(node) if node else (uri.rsplit("#", 1)[-1] or uri)
    return {
        "uri": uri,
        "name": name,
        "description": props.get("description") or props.get("rdfs:comment"),
        "format": props.get("format", "unknown"),
        "status": "external",
        "version": props.get("version") or props.get("owl:versionInfo"),
        "class_count": 0,
        "concept_count": 0,
        "property_count": 0,
        "loaded_at": props.get("loaded_at", ""),
        "enabled": True,
        "tags": [],
        "source_url": None,
    }


def list_registry(
    registry: dict[str, Any],
    session: Any,
    *,
    versions: dict[str, Any] | None = None,
    q: str | None = None,
    status: str | None = None,
    format: str | None = None,
) -> list[dict[str, Any]]:
    all_nodes, _ = session.get_nodes(skip=0, limit=999_999)

    class_counts: dict[str, int] = {}
    concept_counts: dict[str, int] = {}
    prop_counts: dict[str, int] = {}
    implicit: dict[str, dict[str, Any]] = {}
    known_ontology_uris = {
        str(_entry_field(entry, "uri", "")).strip()
        for entry in registry.values()
        if str(_entry_field(entry, "uri", "")).strip()
    }
    published_by_ontology = {
        ouri: published_entity_uris_for_ontology(versions, ouri) for ouri in known_ontology_uris
    }

    def _count_entity(etype: str, bucket: str) -> None:
        if etype == "class":
            class_counts[bucket] = class_counts.get(bucket, 0) + 1
        elif etype == "concept":
            concept_counts[bucket] = concept_counts.get(bucket, 0) + 1
        elif etype == "property":
            prop_counts[bucket] = prop_counts.get(bucket, 0) + 1

    for node in all_nodes:
        ntype = node.get("type", "")
        nid = node.get("id", "")
        etype = _classify_node_type(ntype)

        if etype == "ontology" or etype == "scheme":
            if nid and nid not in registry:
                implicit[nid] = node
            continue

        if etype not in {"class", "concept", "property"}:
            continue

        owner = _node_source_ontology(node)
        props = node.get("properties", {}) or {}
        if not owner:
            owner = props.get("uri") if isinstance(props.get("uri"), str) else None

        bucket: str | None = str(owner).strip() if owner else None
        if not bucket and known_ontology_uris:
            for ontology_uri in sorted(known_ontology_uris, key=len, reverse=True):
                if _node_belongs_to_ontology(
                    node,
                    ontology_uri,
                    known_ontology_uris,
                    published_entity_uris=published_by_ontology.get(ontology_uri),
                ):
                    bucket = ontology_uri
                    break
        if bucket:
            _count_entity(etype, bucket)

    result: list[dict[str, Any]] = []

    def _matches(name: str, uri: str, desc: str) -> bool:
        if not q:
            return True
        ql = q.lower()
        return any(ql in t.lower() for t in [name, uri, desc] if t)

    for entry in registry.values():
        uri = str(_entry_field(entry, "uri", ""))
        entry_status = _entry_field(entry, "status")
        entry_format = _entry_field(entry, "format", "unknown")
        name = _entry_field(entry, "name", "")
        desc = _entry_field(entry, "description", "") or ""

        if status and entry_status != status:
            continue
        if format and str(entry_format).lower() != format.lower():
            continue
        if not _matches(str(name), uri, str(desc)):
            continue
        result.append(
            _dump_entry(
                entry,
                class_count=class_counts.get(uri, _entry_field(entry, "class_count", 0)),
                concept_count=concept_counts.get(uri, _entry_field(entry, "concept_count", 0)),
                property_count=prop_counts.get(uri, _entry_field(entry, "property_count", 0)),
            )
        )

    for nid, node in implicit.items():
        props = node.get("properties", {})
        name = _node_label(node) or nid
        if not _matches(name, nid, props.get("description", "")):
            continue
        result.append(
            {
                "uri": nid,
                "name": name,
                "description": props.get("description"),
                "format": props.get("format", "unknown"),
                "status": "external",
                "version": props.get("version") or props.get("owl:versionInfo"),
                "class_count": class_counts.get(nid, 0),
                "concept_count": concept_counts.get(nid, 0),
                "property_count": prop_counts.get(nid, 0),
                "loaded_at": props.get("loaded_at", ""),
                "enabled": True,
                "tags": [],
            }
        )

    return result


def upsert_alignment(
    align_store: dict[str, Any],
    session: Any,
    *,
    source_uri: str,
    target_uri: str,
    relation: str,
    source_label: str | None = None,
    target_label: str | None = None,
    confidence: float = 1.0,
    provenance: str | None = None,
    source: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    if relation not in _ALIGNMENT_RELATIONS:
        raise AdminError(422, "validation_error", f"Unsupported alignment relation: {relation}")

    source_node = session.get_node(source_uri)
    target_node = session.get_node(target_uri)
    resolved_source_label = (
        source_label
        or (_node_label(source_node) if source_node is not None else None)
        or _label_from_uri(source_uri)
    )
    resolved_target_label = (
        target_label
        or (_node_label(target_node) if target_node is not None else None)
        or _label_from_uri(target_uri)
    )

    now = datetime.now(timezone.utc).isoformat()
    alignment_id = _alignment_id(source_uri, relation, target_uri)
    existing = align_store.get(alignment_id)
    created_at = getattr(existing, "created_at", None) or (
        existing.get("created_at") if isinstance(existing, dict) else None
    ) or now

    alignment = {
        "id": alignment_id,
        "source_uri": source_uri,
        "source_label": resolved_source_label,
        "target_uri": target_uri,
        "target_label": resolved_target_label,
        "relation": relation,
        "predicate_uri": _ALIGNMENT_RELATIONS[relation],
        "confidence": confidence,
        "provenance": provenance,
        "source": source,
        "reviewer": reviewer,
        "created_at": created_at,
        "updated_at": now,
    }
    align_store[alignment_id] = alignment
    return alignment


def delete_alignment(align_store: dict[str, Any], alignment_id: str) -> dict[str, str]:
    if alignment_id not in align_store:
        raise AdminError(404, "not_found", "Alignment not found.")
    del align_store[alignment_id]
    return {"status": "removed", "id": alignment_id}


def suggest_alignments(
    session: Any,
    *,
    source_ontology_uri: str | None = None,
    target_ontology_uri: str | None = None,
    threshold: float = 0.65,
    limit: int = 25,
) -> list[dict[str, Any]]:
    nodes, total_count = session.get_nodes(skip=0, limit=_MAX_ANALYSIS_NODES)
    if total_count > _MAX_ANALYSIS_NODES:
        logger.warning(
            "suggest-alignments: graph has %d nodes; analysis capped at %d.",
            total_count,
            _MAX_ANALYSIS_NODES,
        )
    source_nodes = _ontology_entities(nodes, source_ontology_uri)
    target_nodes = _ontology_entities(nodes, target_ontology_uri)
    if not source_ontology_uri:
        source_nodes = _ontology_entities(nodes)
    if not target_ontology_uri:
        target_nodes = _ontology_entities(nodes)

    if len(source_nodes) > _MAX_ENTITIES_PER_SIDE:
        source_nodes = source_nodes[:_MAX_ENTITIES_PER_SIDE]
    if len(target_nodes) > _MAX_ENTITIES_PER_SIDE:
        target_nodes = target_nodes[:_MAX_ENTITIES_PER_SIDE]

    all_entities = source_nodes + target_nodes
    all_labels = list({_node_label(n) for n in all_entities if _node_label(n)})
    embeddings = _tfidf_embedding_vectors(all_labels)
    has_embeddings = embeddings is not None

    target_token_sets = {n.get("id", ""): _token_set(_node_label(n)) for n in target_nodes}

    suggestions: list[dict[str, Any]] = []
    for source_node in source_nodes:
        source_id = source_node.get("id", "")
        source_label = _node_label(source_node)
        source_ontology = _node_source_ontology(source_node)
        source_tokens = _token_set(source_label)
        source_vec = embeddings.get(source_label) if has_embeddings and embeddings else None

        for target_node in target_nodes:
            target_id = target_node.get("id", "")
            if not source_id or source_id == target_id:
                continue
            target_ontology = _node_source_ontology(target_node)
            if source_ontology and target_ontology and source_ontology == target_ontology:
                continue

            target_tokens = target_token_sets.get(target_id, frozenset())
            if source_tokens and target_tokens and not (source_tokens & target_tokens):
                continue

            target_label = _node_label(target_node)
            label_score = _label_similarity(source_label, target_label)

            embedding_sim: float | None = None
            if has_embeddings and source_vec is not None and embeddings:
                target_vec = embeddings.get(target_label)
                if target_vec is not None:
                    try:
                        embedding_sim = round(_cosine_sim(source_vec, target_vec), 4)
                    except Exception:
                        embedding_sim = None

            if embedding_sim is not None:
                score = round(0.4 * label_score + 0.6 * embedding_sim, 4)
                reason = (
                    f"Label similarity {label_score:.2f}, embedding cosine similarity {embedding_sim:.2f} "
                    f"(TF-IDF character n-gram vectors via SimilarityCalculator)."
                )
            else:
                score = label_score
                reason = f"Label similarity {label_score:.2f}; embedding vectors unavailable."

            if score < threshold:
                continue

            relation = _candidate_relation(source_node, target_node)
            suggestions.append(
                {
                    "source_uri": source_id,
                    "source_label": source_label,
                    "target_uri": target_id,
                    "target_label": target_label,
                    "relation": relation,
                    "score": score,
                    "label_similarity": label_score,
                    "embedding_similarity": embedding_sim,
                    "reason": reason,
                }
            )

    suggestions.sort(key=lambda item: item["score"], reverse=True)
    return suggestions[:limit]
