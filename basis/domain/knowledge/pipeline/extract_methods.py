"""Product-supported entity/relation extract backends (LLM only)."""

from __future__ import annotations

from basis.domain.errors import AdminError

EXTRACT_LLM_METHOD = "llm"


def normalize_ner_method(value: str | None, *, extract: bool) -> str:
    """Coerce to ``llm`` when not extracting; reject non-LLM when ``extract`` is true."""
    method = (value or EXTRACT_LLM_METHOD).strip().lower()
    if not extract:
        return EXTRACT_LLM_METHOD
    if method != EXTRACT_LLM_METHOD:
        raise AdminError(
            422,
            "unsupported_extract_method",
            "实体与关系抽取仅支持对话模型（llm），请在「模型」页配置 Chat",
        )
    return EXTRACT_LLM_METHOD


def normalize_relation_method(value: str | None, *, extract: bool) -> str:
    return normalize_ner_method(value, extract=extract)
