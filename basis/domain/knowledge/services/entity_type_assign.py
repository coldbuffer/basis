"""Direct rdf:type assignment for ledger entities or graph node ids."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.persistence import sql_entities as entity_persist
from basis.domain.knowledge.persistence import sql_typed_facts as typed_persist
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.ontology.mappings.access import RDF_TYPE_URI

_MAX_BATCH = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _label_from_subject_id(subject_id: str) -> str:
    text = str(subject_id or "").strip()
    if not text:
        return text
    if ":" in text:
        return text.rsplit(":", 1)[-1]
    if "/" in text:
        return text.rsplit("/", 1)[-1]
    return text


def _ensure_subject_entity(knowledge: KnowledgeStore, workspace_id: str, subject_id: str) -> str:
    subject = str(subject_id or "").strip()
    if not subject:
        raise AdminError(422, "validation_error", "subject_id is required")
    with knowledge._lock:
        knowledge._assert_workspace_exists(workspace_id)
        conn = knowledge._conn
        if entity_persist.active_entity_exists(conn, workspace_id, subject):
            return subject
        label = _label_from_subject_id(subject)
        entity_persist.insert_entity(
            conn,
            entity_id=subject,
            workspace_id=workspace_id,
            canonical_label=label or subject,
            description="Ensured for rdf:type assignment (graph/ontology subject)",
            entity_kind="named",
            created_at=_now(),
        )
        conn.commit()
    return subject


def assign_entity_type(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    subject_id: str,
    class_uri: str,
    replace_existing: bool = True,
    bump_revision: bool = True,
) -> dict[str, Any]:
    subject = str(subject_id or "").strip()
    class_ref = str(class_uri or "").strip()
    if not subject:
        raise AdminError(422, "validation_error", "subject_id is required")
    if not class_ref:
        raise AdminError(422, "validation_error", "class_uri is required")

    subject = _ensure_subject_entity(knowledge, workspace_id, subject_id)
    now = _now()
    fact_id = str(uuid.uuid4())
    with knowledge._lock:
        knowledge._assert_workspace_exists(workspace_id)
        conn = knowledge._conn
        if replace_existing:
            typed_persist.invalidate_active_typed_facts_for_predicate(
                conn, workspace_id, subject, RDF_TYPE_URI, now
            )
        typed_persist.insert_direct_typed_fact(
            conn,
            fact_id=fact_id,
            workspace_id=workspace_id,
            subject_id=subject,
            predicate_uri=RDF_TYPE_URI,
            object_entity_id=None,
            object_value=class_ref,
            recorded_at=now,
        )
        conn.commit()
    if bump_revision:
        knowledge.bump_projection_revision(workspace_id)
    return {"created": 1, "fact_id": fact_id, "subject_id": subject, "class_uri": class_ref}


def assign_entity_types_batch(
    knowledge: KnowledgeStore,
    workspace_id: str,
    assignments: list[dict[str, Any]],
    *,
    replace_existing: bool = True,
) -> dict[str, Any]:
    if not assignments:
        raise AdminError(422, "validation_error", "assignments is required")
    if len(assignments) > _MAX_BATCH:
        raise AdminError(422, "validation_error", f"assignments exceeds max {_MAX_BATCH}")

    created = 0
    fact_ids: list[str] = []
    errors: list[dict[str, str]] = []
    bumped = False
    for index, raw in enumerate(assignments):
        subject = str(raw.get("subject_id") or raw.get("subject") or "").strip()
        class_uri = str(raw.get("class_uri") or raw.get("object") or "").strip()
        if not subject or not class_uri:
            errors.append({"index": str(index), "error": "subject_id and class_uri required"})
            continue
        try:
            result = assign_entity_type(
                knowledge,
                workspace_id,
                subject_id=subject,
                class_uri=class_uri,
                replace_existing=replace_existing,
                bump_revision=False,
            )
            created += int(result.get("created", 0))
            fact_ids.append(str(result["fact_id"]))
        except AdminError as exc:
            errors.append({"index": str(index), "error": exc.message})

    if created > 0:
        knowledge.bump_projection_revision(workspace_id)
        bumped = True
    return {
        "created": created,
        "fact_ids": fact_ids,
        "errors": errors,
        "projection_revision_bumped": bumped,
    }


def clear_entity_type(
    knowledge: KnowledgeStore,
    workspace_id: str,
    *,
    subject_id: str,
    bump_revision: bool = True,
) -> dict[str, Any]:
    subject = str(subject_id or "").strip()
    if not subject:
        raise AdminError(422, "validation_error", "subject_id is required")
    now = _now()
    with knowledge._lock:
        knowledge._assert_workspace_exists(workspace_id)
        conn = knowledge._conn
        invalidated = typed_persist.invalidate_active_typed_facts_for_predicate(
            conn, workspace_id, subject, RDF_TYPE_URI, now
        )
        conn.commit()
    if bump_revision and invalidated > 0:
        knowledge.bump_projection_revision(workspace_id)
    return {"invalidated": invalidated, "subject_id": subject}


def clear_entity_types_batch(
    knowledge: KnowledgeStore,
    workspace_id: str,
    subject_ids: list[str],
) -> dict[str, Any]:
    if not subject_ids:
        raise AdminError(422, "validation_error", "subject_ids is required")
    if len(subject_ids) > _MAX_BATCH:
        raise AdminError(422, "validation_error", f"subject_ids exceeds max {_MAX_BATCH}")

    total = 0
    errors: list[dict[str, str]] = []
    bumped = False
    for index, raw in enumerate(subject_ids):
        subject = str(raw or "").strip()
        if not subject:
            errors.append({"index": str(index), "error": "subject_id required"})
            continue
        try:
            result = clear_entity_type(
                knowledge,
                workspace_id,
                subject_id=subject,
                bump_revision=False,
            )
            total += int(result.get("invalidated", 0))
        except AdminError as exc:
            errors.append({"index": str(index), "error": exc.message})

    if total > 0:
        knowledge.bump_projection_revision(workspace_id)
        bumped = True
    return {
        "invalidated": total,
        "errors": errors,
        "projection_revision_bumped": bumped,
    }
