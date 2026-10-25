"""Graph semantic duplicate detection for agent governor (F-GOV-04 Phase D)."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.services.governor_cluster import ENTITY_CLUSTER_KIND, ENTITY_CLUSTER_SUBJECT_TYPE
from basis.domain.knowledge.store import KnowledgeStore

DEFAULT_GOVERNOR_DEDUP_THRESHOLD = 0.8


def _extract_dedup_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    if isinstance(value, dict):
        for key in ("id", "entity_id", "text"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return None


def _similarity_score(pair: dict[str, Any]) -> float | None:
    for key in ("similarity", "score", "similarity_score"):
        raw = pair.get(key)
        if isinstance(raw, (int, float)):
            return float(raw)
    return None


def _normalize_dedup_pair(raw: Any) -> dict[str, Any] | None:
    """Accept dict or Semantica ``DuplicateCandidate`` (governor used to drop non-dicts)."""
    if isinstance(raw, dict):
        return raw
    entity1 = getattr(raw, "entity1", None)
    entity2 = getattr(raw, "entity2", None)
    if entity1 is None or entity2 is None:
        return None
    similarity = getattr(raw, "similarity_score", None)
    if similarity is None:
        similarity = getattr(raw, "similarity", None)
    out: dict[str, Any] = {"entity1": entity1, "entity2": entity2}
    if isinstance(similarity, (int, float)):
        out["similarity"] = float(similarity)
        out["score"] = float(similarity)
    return out


async def _detect_duplicate_pairs(session: Any, threshold: float) -> list[dict[str, Any]]:
    from semantica.deduplication import DuplicateDetector

    detector = DuplicateDetector()
    nodes, _ = await asyncio.to_thread(session.get_nodes, skip=0, limit=999_999)
    entities = [
        {
            "id": node.get("id"),
            "text": node.get("content", node.get("id", "")),
            "type": node.get("type", "entity"),
        }
        for node in nodes
    ]
    duplicates = await asyncio.to_thread(detector.detect_duplicates, entities, threshold=threshold)
    if isinstance(duplicates, list):
        return duplicates
    nested = getattr(duplicates, "duplicates", None)
    return list(nested) if nested else []


async def scan_graph_semantic_dedup_clusters(
    knowledge: KnowledgeStore,
    workspace_id: str,
    session: Any,
    *,
    threshold: float = DEFAULT_GOVERNOR_DEDUP_THRESHOLD,
) -> dict[str, Any]:
    """Enqueue ``entity_cluster`` items from graph embedding/text dedup pairs."""
    if not 0.0 <= threshold <= 1.0:
        raise AdminError(422, "bad_dedup_threshold", "dedup_threshold 须在 0–1 之间")
    try:
        pairs = await _detect_duplicate_pairs(session, threshold)
    except ImportError:
        return {"created": 0, "skipped": 0, "unavailable": True}
    created: list[str] = []
    skipped = 0
    for raw_pair in pairs:
        pair = _normalize_dedup_pair(raw_pair)
        if not pair:
            continue
        left = _extract_dedup_id(pair.get("entity_a") or pair.get("entity1"))
        right = _extract_dedup_id(pair.get("entity_b") or pair.get("entity2"))
        if not left or not right or left == right:
            skipped += 1
            continue
        entity_ids = sorted([left, right])
        subject_id = hashlib.sha256(f"{entity_ids[0]}:{entity_ids[1]}".encode()).hexdigest()[:32]
        payload: dict[str, Any] = {
            "source": "graph_semantic_dedup",
            "entity_ids": entity_ids,
            "suggested_primary_id": entity_ids[0],
            "similarity": _similarity_score(pair),
            "graph_node_ids": entity_ids,
        }
        try:
            item = knowledge.create_review_item(
                workspace_id,
                kind=ENTITY_CLUSTER_KIND,
                subject_type=ENTITY_CLUSTER_SUBJECT_TYPE,
                subject_id=subject_id,
                payload=payload,
                priority=4,
            )
            created.append(item["id"])
        except AdminError as exc:
            if exc.code == "review_exists":
                skipped += 1
                continue
            raise
    return {"created": len(created), "skipped": skipped, "item_ids": created}
