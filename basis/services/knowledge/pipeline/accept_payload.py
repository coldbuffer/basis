"""Stable JSON bodies for accepted document ingest jobs."""

from __future__ import annotations

from typing import Any


def ingest_accept_payload(
    *,
    job_id: str,
    version_id: str,
    ledger_document_id: str,
    doc_id: str,
    filename: str,
) -> dict[str, Any]:
    return {
        "accepted": True,
        "status": "queued",
        "job_id": job_id,
        "version_id": version_id,
        "document_id": ledger_document_id,
        "doc_id": doc_id,
        "filename": filename,
    }
