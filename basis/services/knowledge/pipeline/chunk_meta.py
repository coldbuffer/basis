"""Chunk rows written by ingest: text plus the source fields the ledger already has columns for."""

from __future__ import annotations

import json
import re
from typing import Any

from basis.services.knowledge.pipeline.document import TextIngestOptions

_HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)\s*$", re.MULTILINE)
_CJK = re.compile(r"[\u4e00-\u9fff]")
_KANA = re.compile(r"[\u3040-\u30ff]")
_HANGUL = re.compile(r"[\uac00-\ud7af]")
_LATIN = re.compile(r"[A-Za-z]")
_WORD = re.compile(r"[A-Za-z0-9]+")

_encoder: Any = None
_encoder_checked = False


def prepare_chunks(full_text: str, options: TextIngestOptions) -> list[dict[str, Any]]:
    """Split ``full_text`` and attach heading, offsets, token count, language, and an anchor."""
    if not full_text.strip():
        return []
    pieces = _pieces(full_text, options)
    headings = [(match.start(), match.group(1).strip()) for match in _HEADING.finditer(full_text)]
    rows: list[dict[str, Any]] = []
    for text, char_start, char_end in pieces:
        if not text.strip():
            continue
        heading = _heading_at(headings, char_start)
        anchor: dict[str, Any] = {"char_start": char_start, "char_end": char_end}
        if heading:
            anchor["heading"] = heading
        rows.append(
            {
                "text": text,
                "heading": heading,
                "char_start": char_start,
                "char_end": char_end,
                "token_count": token_count(text),
                "language": detect_language(text),
                "origin": "stated",
                "anchor_json": json.dumps(anchor, ensure_ascii=False),
            }
        )
    return rows


def token_count(text: str) -> int:
    if not text:
        return 0
    encoder = _tiktoken()
    if encoder is not None:
        return len(encoder.encode(text))
    cjk = len(_CJK.findall(text)) + len(_KANA.findall(text)) + len(_HANGUL.findall(text))
    words = len(_WORD.findall(text))
    return cjk + words


def detect_language(text: str) -> str | None:
    sample = text[:4000]
    zh = len(_CJK.findall(sample))
    ja = len(_KANA.findall(sample))
    ko = len(_HANGUL.findall(sample))
    en = len(_LATIN.findall(sample))
    if ja >= 3 and ja >= ko and zh + ja >= en:
        return "ja"
    counts = {"zh": zh, "ko": ko, "en": en}
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        return None
    return best


def _pieces(full_text: str, options: TextIngestOptions) -> list[tuple[str, int, int]]:
    if not options.chunk or len(full_text) <= options.chunk_size:
        return [(full_text, 0, len(full_text))]
    from basis.services.knowledge.pipeline.chunk_split import text_splitter

    splitter = text_splitter(options)
    pieces: list[tuple[str, int, int]] = []
    for part in splitter.split(full_text):
        text = getattr(part, "text", "") or ""
        if not text.strip():
            continue
        start_index = int(getattr(part, "start_index", 0) or 0)
        end_index = int(getattr(part, "end_index", start_index + len(text)) or 0)
        char_start, char_end = _locate(full_text, text, start_index, end_index)
        pieces.append((text, char_start, char_end))
    return pieces or [(full_text, 0, len(full_text))]


def _locate(full_text: str, chunk_text: str, start_index: int, end_index: int) -> tuple[int, int]:
    window = full_text[start_index:end_index]
    pos = window.find(chunk_text)
    if pos >= 0:
        char_start = start_index + pos
    else:
        pos = full_text.find(chunk_text, start_index)
        char_start = pos if pos >= 0 else start_index
    return char_start, char_start + len(chunk_text)


def _heading_at(headings: list[tuple[int, str]], index: int) -> str | None:
    current: str | None = None
    for pos, title in headings:
        if pos <= index:
            current = title
        else:
            break
    return current


def _tiktoken() -> Any:
    global _encoder, _encoder_checked
    if not _encoder_checked:
        _encoder_checked = True
        try:
            import tiktoken

            _encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _encoder = None
    return _encoder
