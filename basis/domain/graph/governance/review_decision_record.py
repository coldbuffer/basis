"""Human-readable graph decision payloads for review approve actions."""

from __future__ import annotations

from typing import Any

from basis.domain.knowledge.store import KnowledgeStore


def _label(
    knowledge: KnowledgeStore,
    workspace_id: str,
    entity_id: str,
    cache: dict[str, str | None],
) -> str:
    if entity_id not in cache:
        cache.update(knowledge.entity_labels_by_ids(workspace_id, [entity_id]))
    return (cache.get(entity_id) or "").strip() or entity_id


def build_entity_merge_decision(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    review_item_id: str,
    primary_id: str,
    duplicate_ids: list[str],
    rationale: str | None,
    merge_result: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any]]:
    """Return (scenario, reasoning prose, metadata detail)."""
    label_cache: dict[str, str | None] = {}
    primary_label = _label(knowledge, workspace_id, primary_id, label_cache)
    dup_labels = [_label(knowledge, workspace_id, d, label_cache) for d in duplicate_ids]
    scenario = (
        f"实体合并：保留「{primary_label}」，合并 {len(duplicate_ids)} 个重复实体"
        if duplicate_ids
        else f"实体合并：保留「{primary_label}」"
    )
    lines = [
        f"主实体：{primary_label}（{primary_id}）",
    ]
    if duplicate_ids:
        lines.append(
            "合并入："
            + "；".join(f"「{lab}」（{eid}）" for lab, eid in zip(dup_labels, duplicate_ids, strict=False))
        )
    if rationale and rationale.strip():
        lines.append(f"审核说明：{rationale.strip()}")
    if merge_result:
        mode = merge_result.get("mode")
        if mode == "ledger_rebuild":
            lines.append("执行方式：账本 entity_merges 记录并重建图投影。")
        notice = merge_result.get("ledger_notice")
        if notice == "graph_only_merge":
            lines.append("执行方式：仅更新图投影（重复项未入账本，未写入 entity_merges）。")
        elif notice == "partial_ledger":
            skipped = merge_result.get("ledger_skipped_ids") or []
            lines.append(f"执行方式：部分账本合并；未入账本节点：{', '.join(skipped)}")
        edges = merge_result.get("edges_updated")
        if isinstance(edges, int):
            lines.append(f"图边重定向：{edges} 条")
    detail: dict[str, Any] = {
        "kind": "entity_merge",
        "review_item_id": review_item_id,
        "primary_id": primary_id,
        "duplicate_ids": duplicate_ids,
        "primary_label": primary_label,
        "duplicate_labels": dict(zip(duplicate_ids, dup_labels, strict=False)),
        "summary": scenario,
    }
    return scenario, "\n".join(lines), detail


def build_entity_cluster_promote_decision(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    review_item_id: str,
    primary_id: str,
    duplicate_ids: list[str],
    cluster_payload: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    label_cache: dict[str, str | None] = {}
    primary_label = _label(knowledge, workspace_id, primary_id, label_cache)
    source = str(cluster_payload.get("source") or "")
    if source == "graph_semantic_dedup":
        scenario = f"图语义去重：选定「{primary_label}」为主实体，提交实体合并审核"
    else:
        canonical = str(cluster_payload.get("canonical_label") or primary_label)
        scenario = f"重复标签聚类：「{canonical}」— 选定「{primary_label}」为主实体"
    dup_labels = [_label(knowledge, workspace_id, d, label_cache) for d in duplicate_ids]
    lines = [
        scenario,
        f"主实体：{primary_label}（{primary_id}）",
    ]
    if duplicate_ids:
        lines.append(
            "待合并："
            + "；".join(f"「{lab}」（{eid}）" for lab, eid in zip(dup_labels, duplicate_ids, strict=False))
        )
    sim = cluster_payload.get("similarity")
    if isinstance(sim, (int, float)):
        lines.append(f"相似度：{float(sim):.2f}")
    detail = {
        "kind": "entity_cluster",
        "review_item_id": review_item_id,
        "primary_id": primary_id,
        "duplicate_ids": duplicate_ids,
        "primary_label": primary_label,
        "duplicate_labels": dict(zip(duplicate_ids, dup_labels, strict=False)),
        "cluster_source": source or None,
        "summary": scenario,
    }
    return scenario, "\n".join(lines), detail
