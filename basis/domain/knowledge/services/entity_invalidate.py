"""Batch soft-invalidate ledger entities (temporal ledger; rebuild projection)."""

from __future__ import annotations

from datetime import datetime, timezone

from basis.domain.errors import AdminError
from basis.domain.knowledge.store import KnowledgeStore

_MAX_BATCH = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def invalidate_entities_batch(
    knowledge: KnowledgeStore,
    workspace_id: str,
    entity_ids: list[str],
) -> dict:
    if not entity_ids:
        raise AdminError(422, "validation_error", "entity_ids is required")
    if len(entity_ids) > _MAX_BATCH:
        raise AdminError(422, "validation_error", f"entity_ids exceeds max {_MAX_BATCH}")

    now = _now()
    results: list[dict] = []
    errors: list[dict[str, str]] = []
    changed = 0
    for index, raw in enumerate(entity_ids):
        entity_id = str(raw or "").strip()
        if not entity_id:
            errors.append({"index": str(index), "error": "entity_id required"})
            continue
        try:
            outcome = knowledge.invalidate_entity(workspace_id, entity_id, invalidated_at=now)
            results.append(outcome)
            if not outcome.get("already_invalidated"):
                changed += 1
        except AdminError as exc:
            errors.append({"index": str(index), "entity_id": entity_id, "error": exc.message})

    bumped = False
    if changed > 0:
        knowledge.bump_projection_revision(workspace_id)
        bumped = True
    return {
        "invalidated": changed,
        "results": results,
        "errors": errors,
        "projection_revision_bumped": bumped,
    }
