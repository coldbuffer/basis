"""Map Basis ingest options to semantica GraphBuilder.build kwargs (F-SRC-05)."""

from __future__ import annotations

from typing import Any

from basis.domain.errors import AdminError
from basis.domain.knowledge.pipeline.document import TextIngestOptions
def uses_llm_extraction(options: TextIngestOptions) -> bool:
    return options.extract


def _resolved_llm_model(
    options: TextIngestOptions,
    chat_llm: dict[str, str | None],
) -> str:
    override = (options.llm_model or "").strip()
    if override:
        return override
    return (chat_llm.get("model") or "").strip()


def validate_extract_options(
    options: TextIngestOptions,
    chat_llm: dict[str, str | None],
) -> None:
    """Reject extraction when platform Chat credentials or per-job model are missing."""
    if not options.extract:
        return
    api_key = (chat_llm.get("api_key") or "").strip()
    model = _resolved_llm_model(options, chat_llm)
    if api_key and model:
        return
    if not api_key:
        raise AdminError(
            422,
            "chat_not_configured",
            "LLM 抽取需要先在「管理 → 模型」配置 Chat API Key",
        )
    raise AdminError(
        422,
        "extract_model_required",
        "请选择用于抽取的对话模型",
    )


def semantica_build_kwargs(
    options: TextIngestOptions,
    chat_llm: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "extract": options.extract,
        "ner_method": options.ner_method,
        "relation_method": options.relation_method,
        "extract_relations": options.extract_relations,
        # Relation extraction already writes the graph edges. Triplet extraction
        # only duplicated them, so it stays off.
        "extract_triplets": False,
    }
    if options.extract and chat_llm:
        api_key = (chat_llm.get("api_key") or "").strip()
        model = _resolved_llm_model(options, chat_llm)
        if api_key and model:
            kwargs["provider"] = "openai"
            kwargs["api_key"] = api_key
            kwargs["llm_model"] = model
            base_url = (chat_llm.get("base_url") or "").strip()
            if base_url:
                kwargs["base_url"] = base_url
    return kwargs
