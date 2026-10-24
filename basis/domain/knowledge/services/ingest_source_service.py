"""Shared ingest-source helpers (webhook, URL pull)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI

from basis.domain.errors import AdminError
from basis.domain.knowledge.services.alerts_emit import _with_episode
from basis.domain.knowledge.store import KnowledgeStore
from basis.domain.knowledge.pipeline.document import TextIngestOptions

_HTTP_POLL_TIMEOUT = 30.0
_HTTP_POLL_MAX_BYTES = 5 * 1024 * 1024

_GITHUB_REPO_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)

_DEFAULT_PROCESSING_OPTIONS = {
    "chunk": True,
    "chunk_method": "recursive",
    "chunk_size": 1800,
    "chunk_overlap": 250,
    "extract": True,
    "ner_method": "llm",
    "relation_method": "llm",
    "extract_relations": True,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _doc_id_from_external_key(external_key: str | None, title: str) -> str:
    if external_key and external_key.strip():
        return external_key.strip()
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", (title or "ingest").strip()).strip("-._")
    return stem or f"ingest-{uuid.uuid4().hex[:12]}"


def is_ingest_poll_due(source: dict[str, Any], now: datetime) -> bool:
    config = source.get("config") or {}
    interval = int(config.get("poll_interval_minutes") or 0)
    if interval <= 0:
        return False
    last = config.get("last_sync_at")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    elapsed = (now - last_dt).total_seconds()
    return elapsed >= interval * 60


is_http_poll_due = is_ingest_poll_due


def git_raw_urls(repo_url: str, branch: str, paths: list[str]) -> list[str]:
    match = _GITHUB_REPO_RE.match(repo_url.strip())
    if not match:
        raise AdminError(422, "unsupported_repo", "仅支持 GitHub HTTPS 仓库 URL")
    org, repo = match.group(1), match.group(2)
    ref = (branch or "main").strip() or "main"
    urls: list[str] = []
    for path in paths:
        rel = str(path).strip().lstrip("/")
        if rel:
            urls.append(f"https://raw.githubusercontent.com/{org}/{repo}/{ref}/{rel}")
    if not urls:
        raise AdminError(422, "bad_paths", "至少配置一个仓库内文件路径")
    return urls


def fetch_git_sync_text(repo_url: str, branch: str, paths: list[str]) -> str:
    chunks = [fetch_http_poll_text(url) for url in git_raw_urls(repo_url, branch, paths)]
    return "\n\n---\n\n".join(chunks)


def record_ingest_source_event(
    knowledge: KnowledgeStore,
    workspace_id: str,
    source_id: str,
    event: dict[str, Any],
    *,
    max_events: int = 30,
) -> None:
    source = knowledge.get_ingest_source(workspace_id, source_id)
    config = dict(source.get("config") or {})
    events = list(config.get("sync_events") or [])
    events.insert(0, event)
    config["sync_events"] = events[:max_events]
    config["last_sync_at"] = event.get("at")
    config["last_sync_status"] = event.get("status")
    knowledge.update_ingest_source(workspace_id, source_id, config=config)
    if event.get("status") == "failed":
        mode = str(event.get("mode") or source.get("kind") or "source")
        err = str(event.get("error") or "")[:400]
        knowledge.create_workspace_alert(
            workspace_id,
            kind="sync_failed",
            message=f"Connector sync failed ({mode})",
            severity="warning",
            detail=_with_episode(
                {
                    "source_id": source_id,
                    "source_name": source.get("name"),
                    "mode": mode,
                    "error": err or None,
                },
                f"sync:{source_id}",
            ),
        )


def fetch_http_poll_text(url: str) -> str:
    try:
        with httpx.Client(timeout=_HTTP_POLL_TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
        response.raise_for_status()
        raw = response.content
        if len(raw) > _HTTP_POLL_MAX_BYTES:
            raise AdminError(413, "payload_too_large", "响应体过大")
        text = raw.decode(response.encoding or "utf-8", errors="replace").strip()
        if not text:
            raise AdminError(422, "empty_body", "URL 返回空内容")
        return text
    except AdminError:
        raise
    except Exception as exc:
        raise AdminError(502, "fetch_failed", "拉取 URL 失败") from exc


def enqueue_text_from_source(
    app: FastAPI,
    knowledge: KnowledgeStore,
    workspace_id: str,
    source_id: str,
    *,
    title: str,
    text: str,
    doc_id: str,
    auto_process: bool,
) -> dict[str, Any]:
    from basis.domain.knowledge.pipeline.accept_payload import ingest_accept_payload
    from basis.domain.knowledge.schedulers.version_ingest_tasks import enqueue_version_ingest

    filename = f"{doc_id}.txt"
    outcome = knowledge.store_document_bytes(
        workspace_id,
        title=title,
        mime_type="text/plain",
        data=text.encode("utf-8"),
        created_by=None,
        original_filename=filename,
        external_key=doc_id,
        source_id=source_id,
    )
    if not auto_process:
        return {
            "accepted": True,
            "document_id": outcome.document_id,
            "version_id": outcome.version_id,
            "doc_id": doc_id,
            "status": "uploaded",
        }
    options = TextIngestOptions(**_DEFAULT_PROCESSING_OPTIONS)
    job, _ = knowledge.create_processing_job(
        workspace_id,
        version_id=outcome.version_id,
        options=_DEFAULT_PROCESSING_OPTIONS,
    )
    enqueue_version_ingest(
        app,
        workspace_id,
        outcome.version_id,
        job["id"],
        filename=filename,
        graph_doc_id=doc_id,
        options=options,
    )
    return ingest_accept_payload(
        job_id=job["id"],
        version_id=outcome.version_id,
        ledger_document_id=outcome.document_id,
        doc_id=doc_id,
        filename=filename,
    )


def execute_http_poll_sync(
    app: FastAPI,
    knowledge: KnowledgeStore,
    workspace_id: str,
    source_id: str,
    *,
    auto_process: bool,
) -> dict[str, Any]:
    source = knowledge.get_ingest_source(workspace_id, source_id)
    if source["kind"] != "http_poll" or not source["enabled"]:
        raise AdminError(403, "forbidden", "来源未启用")
    url = str(source["config"].get("url") or "").strip()
    if not url:
        raise AdminError(422, "bad_url", "未配置 URL")
    at = _now_iso()
    try:
        text = fetch_http_poll_text(url)
    except AdminError:
        record_ingest_source_event(
            knowledge,
            workspace_id,
            source_id,
            {"at": at, "status": "failed", "mode": "http_poll", "url": url},
        )
        raise
    except Exception as exc:
        record_ingest_source_event(
            knowledge,
            workspace_id,
            source_id,
            {
                "at": at,
                "status": "failed",
                "mode": "http_poll",
                "url": url,
                "error": str(exc)[:500],
            },
        )
        raise

    prefix = str(source["config"].get("external_key_prefix") or "poll").strip() or "poll"
    doc_id = _doc_id_from_external_key(f"{prefix}-{uuid.uuid4().hex[:10]}", url)
    title = str(source["config"].get("title") or source["name"] or "HTTP poll")
    result = enqueue_text_from_source(
        app,
        knowledge,
        workspace_id,
        source_id,
        title=title,
        text=text,
        doc_id=doc_id,
        auto_process=auto_process,
    )
    record_ingest_source_event(
        knowledge,
        workspace_id,
        source_id,
        {
            "at": at,
            "status": "succeeded",
            "mode": "http_poll",
            "url": url,
            "doc_id": result.get("doc_id"),
            "job_id": result.get("job_id"),
        },
    )
    return result


def execute_git_sync(
    app: FastAPI,
    knowledge: KnowledgeStore,
    workspace_id: str,
    source_id: str,
    *,
    auto_process: bool,
) -> dict[str, Any]:
    source = knowledge.get_ingest_source(workspace_id, source_id)
    if source["kind"] != "git" or not source["enabled"]:
        raise AdminError(403, "forbidden", "来源未启用")
    config = source.get("config") or {}
    repo_url = str(config.get("repo_url") or "").strip()
    branch = str(config.get("branch") or "main")
    paths = config.get("paths") or []
    if not isinstance(paths, list):
        paths = [str(paths)]
    at = _now_iso()
    try:
        text = fetch_git_sync_text(repo_url, branch, [str(p) for p in paths])
    except AdminError:
        record_ingest_source_event(
            knowledge,
            workspace_id,
            source_id,
            {"at": at, "status": "failed", "mode": "git", "repo_url": repo_url},
        )
        raise
    except Exception as exc:
        record_ingest_source_event(
            knowledge,
            workspace_id,
            source_id,
            {
                "at": at,
                "status": "failed",
                "mode": "git",
                "repo_url": repo_url,
                "error": str(exc)[:500],
            },
        )
        raise

    prefix = str(config.get("external_key_prefix") or "git").strip() or "git"
    doc_id = _doc_id_from_external_key(f"{prefix}-{uuid.uuid4().hex[:10]}", repo_url)
    title = str(config.get("title") or source["name"] or "Git sync")
    result = enqueue_text_from_source(
        app,
        knowledge,
        workspace_id,
        source_id,
        title=title,
        text=text,
        doc_id=doc_id,
        auto_process=auto_process,
    )
    record_ingest_source_event(
        knowledge,
        workspace_id,
        source_id,
        {
            "at": at,
            "status": "succeeded",
            "mode": "git",
            "repo_url": repo_url,
            "doc_id": result.get("doc_id"),
            "job_id": result.get("job_id"),
        },
    )
    return result


def execute_ingest_source_sync(
    app: FastAPI,
    knowledge: KnowledgeStore,
    workspace_id: str,
    source_id: str,
    *,
    auto_process: bool,
) -> dict[str, Any]:
    source = knowledge.get_ingest_source(workspace_id, source_id)
    kind = source["kind"]
    if kind == "http_poll":
        return execute_http_poll_sync(app, knowledge, workspace_id, source_id, auto_process=auto_process)
    if kind == "git":
        return execute_git_sync(app, knowledge, workspace_id, source_id, auto_process=auto_process)
    raise AdminError(422, "not_syncable", "该来源类型不支持手动同步")
