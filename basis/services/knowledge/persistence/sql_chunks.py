"""Chunk rows — canonical DB SQL (caller holds lock)."""

from __future__ import annotations

import json
from typing import Any

from basis.services.errors import AdminError


def first_chunk_id(conn: Any, workspace_id: str, version_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT id FROM chunks
        WHERE workspace_id = ? AND version_id = ?
        ORDER BY ordinal LIMIT 1
        """,
        (workspace_id, version_id),
    ).fetchone()
    return row["id"] if row else None


def first_chunk_text(conn: Any, workspace_id: str, version_id: str) -> Any:
    return conn.execute(
        """
        SELECT text FROM chunks
        WHERE version_id = ? AND workspace_id = ?
        ORDER BY ordinal LIMIT 1
        """,
        (version_id, workspace_id),
    ).fetchone()


def chunk_api_row(row: Any) -> dict[str, Any]:
    anchor_raw = row["anchor_json"]
    anchor: Any = None
    if anchor_raw:
        try:
            anchor = json.loads(anchor_raw)
        except json.JSONDecodeError:
            anchor = None
    return {
        "id": row["id"],
        "ordinal": row["ordinal"],
        "text": row["text"] or "",
        "heading": row["heading"],
        "char_start": row["char_start"],
        "char_end": row["char_end"],
        "token_count": row["token_count"],
        "language": row["language"],
        "origin": row["origin"],
        "anchor": anchor,
        "created_at": row["created_at"],
    }


def chunk_text_row(conn: Any, chunk_id: str) -> Any:
    return conn.execute("SELECT text FROM chunks WHERE id = ?", (chunk_id,)).fetchone()


def validate_quote_in_chunk(
    conn: Any, chunk_id: str, quote: str, quote_start: int, quote_end: int
) -> None:
    if quote_start < 0 or quote_end < quote_start:
        raise AdminError(422, "bad_quote", "引用偏移无效")
    row = chunk_text_row(conn, chunk_id)
    if row is None:
        raise AdminError(404, "not_found", "分块不存在")
    text = row["text"]
    if text[quote_start:quote_end] != quote:
        raise AdminError(422, "quote_not_in_chunk", "引用与分块文本不匹配")


def insert_chunk(
    conn: Any,
    *,
    chunk_id: str,
    workspace_id: str,
    version_id: str,
    ordinal: int,
    text: str,
    heading: str | None,
    char_start: int | None,
    char_end: int | None,
    token_count: int | None,
    language: str | None,
    origin: str,
    anchor_json: str | None,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO chunks(
            id, workspace_id, version_id, ordinal, text, heading,
            char_start, char_end, token_count, language, origin, anchor_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk_id,
            workspace_id,
            version_id,
            ordinal,
            text,
            heading,
            char_start,
            char_end,
            token_count,
            language,
            origin,
            anchor_json,
            created_at,
        ),
    )


def insert_chunks_many(conn: Any, rows: list[tuple[Any, ...]]) -> None:
    conn.executemany(
        """
        INSERT INTO chunks(
            id, workspace_id, version_id, ordinal, text, heading,
            char_start, char_end, token_count, language, origin,
            anchor_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def chunk_payload_from_item(item: str | dict[str, Any]) -> dict[str, Any]:
    raw = {"text": item} if isinstance(item, str) else item
    anchor_json = raw.get("anchor_json")
    anchor = raw.get("anchor")
    if anchor_json is None and isinstance(anchor, dict):
        anchor_json = json.dumps(anchor, ensure_ascii=False)
    return {
        "text": raw.get("text") or "",
        "heading": raw.get("heading"),
        "char_start": raw.get("char_start"),
        "char_end": raw.get("char_end"),
        "token_count": raw.get("token_count"),
        "language": raw.get("language"),
        "origin": raw.get("origin") or "stated",
        "anchor_json": anchor_json,
    }


def fetch_chunk_with_document(conn: Any, workspace_id: str, chunk_id: str) -> Any:
    return conn.execute(
        """
        SELECT c.id, c.text, c.ordinal, c.heading, c.char_start, c.char_end,
               c.token_count, c.language, c.origin, c.anchor_json, c.created_at,
               d.id AS document_id, d.title AS document_title
        FROM chunks c
        INNER JOIN document_versions dv ON dv.id = c.version_id
        INNER JOIN documents d ON d.id = dv.document_id
        WHERE c.id = ? AND c.workspace_id = ?
        """,
        (chunk_id, workspace_id),
    ).fetchone()


def list_chunk_rows(conn: Any, workspace_id: str, version_id: str) -> list[Any]:
    return conn.execute(
        """
        SELECT id, ordinal, text, heading, char_start, char_end,
               token_count, language, origin, anchor_json, created_at
        FROM chunks
        WHERE workspace_id = ? AND version_id = ?
        ORDER BY ordinal
        """,
        (workspace_id, version_id),
    ).fetchall()
