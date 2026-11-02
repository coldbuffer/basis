"""Entity label clustering for agent governor (F-GOV-04 Phase C)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

from basis.services.errors import AdminError
from basis.services.knowledge.store import KnowledgeStore

ENTITY_CLUSTER_KIND = "entity_cluster"
ENTITY_CLUSTER_SUBJECT_TYPE = "entity_group"


def _normalize_label(label: str | None) -> str:
    return " ".join((label or "").strip().lower().split())


def find_entity_label_clusters(knowledge: KnowledgeStore, workspace_id: str) -> list[dict[str, Any]]:
    """Groups of active entities sharing the same normalized canonical label."""
    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in knowledge.list_active_entity_id_labels(workspace_id):
        norm = _normalize_label(row["canonical_label"])
        if not norm:
            continue
        buckets[norm].append(row)
    clusters: list[dict[str, Any]] = []
    for norm, members in buckets.items():
        if len(members) < 2:
            continue
        entity_ids = sorted(m["entity_id"] for m in members)
        clusters.append(
            {
                "canonical_label": members[0]["canonical_label"],
                "canonical_label_normalized": norm,
                "entity_ids": entity_ids,
                "suggested_primary_id": entity_ids[0],
            }
        )
    return clusters


def scan_entity_label_clusters(knowledge: KnowledgeStore, workspace_id: str) -> dict[str, Any]:
    """Enqueue open review items for duplicate-label entity groups."""
    created: list[str] = []
    skipped = 0
    for cluster in find_entity_label_clusters(knowledge, workspace_id):
        subject_id = hashlib.sha256(":".join(cluster["entity_ids"]).encode()).hexdigest()[:32]
        try:
            item = knowledge.create_review_item(
                workspace_id,
                kind=ENTITY_CLUSTER_KIND,
                subject_type=ENTITY_CLUSTER_SUBJECT_TYPE,
                subject_id=subject_id,
                payload=cluster,
                priority=4,
            )
            created.append(item["id"])
        except AdminError as exc:
            if exc.code == "review_exists":
                skipped += 1
                continue
            raise
    return {"created": len(created), "skipped": skipped, "item_ids": created}
