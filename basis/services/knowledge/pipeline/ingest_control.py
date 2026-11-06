"""Cooperative pause flags and restart recovery for document ingest jobs."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from basis.services.errors import AdminError

if TYPE_CHECKING:
    from basis.services.knowledge.store import KnowledgeStore

_PIPELINE_VERSION_STATUSES = frozenset(
    {"queued", "parsing", "chunking", "embedding", "extracting"}
)
_PAUSEABLE_JOB_STATUSES = frozenset({"queued", "running"})

_pause_requested: set[str] = set()
_guard = threading.Lock()


def request_ingest_pause(job_id: str) -> None:
    with _guard:
        _pause_requested.add(job_id)


def clear_ingest_pause(job_id: str) -> None:
    with _guard:
        _pause_requested.discard(job_id)


def ingest_pause_requested(job_id: str) -> bool:
    with _guard:
        return job_id in _pause_requested


def mark_version_paused(knowledge: KnowledgeStore, workspace_id: str, version_id: str) -> None:
    version = knowledge.get_version(workspace_id, version_id)
    if version.status in _PIPELINE_VERSION_STATUSES:
        knowledge.set_version_status(workspace_id, version_id, "paused")


def pause_ingest_job(knowledge: KnowledgeStore, workspace_id: str, job_id: str) -> dict[str, object]:
    """Pause a queued job immediately, or ask a running worker to stop at the next chunk."""
    job = knowledge.get_job(workspace_id, job_id)
    if job.kind != "ingest" or job.subject_type != "document_version":
        raise AdminError(409, "job_not_pausable", "仅排队或运行中的任务可暂停")
    if job.status == "paused":
        return {"job_id": job.id, "status": "paused", "pause_requested": False}
    if job.status not in _PAUSEABLE_JOB_STATUSES:
        raise AdminError(409, "job_not_pausable", "仅排队或运行中的任务可暂停")

    request_ingest_pause(job.id)
    if job.status == "queued" and knowledge.try_transition_job_status(
        workspace_id,
        job.id,
        "paused",
        expect={"queued"},
    ):
        mark_version_paused(knowledge, workspace_id, job.subject_id)
        clear_ingest_pause(job.id)
        return {"job_id": job.id, "status": "paused", "pause_requested": False}

    latest = knowledge.get_job(workspace_id, job.id)
    if latest.status not in _PAUSEABLE_JOB_STATUSES:
        clear_ingest_pause(job.id)
    return {
        "job_id": latest.id,
        "status": latest.status,
        "pause_requested": latest.status in _PAUSEABLE_JOB_STATUSES,
    }


def pause_orphaned_ingest_jobs(knowledge: KnowledgeStore) -> int:
    """Mark ingest jobs still queued or running as paused. No worker survives a process restart."""
    paused = 0
    for workspace_id, job_id, version_id in knowledge.list_live_ingest_jobs():
        if not knowledge.try_transition_job_status(
            workspace_id,
            job_id,
            "paused",
            expect={"queued", "running"},
        ):
            continue
        paused += 1
        mark_version_paused(knowledge, workspace_id, version_id)
    return paused
