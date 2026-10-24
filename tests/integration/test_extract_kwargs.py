"""F-SRC-05: semantica extract kwargs and LLM gate."""

import pytest

from basis.domain.tenancy.admin.errors import AdminError
from basis.domain.knowledge.pipeline.document import TextIngestOptions
from basis.domain.knowledge.pipeline.extract_methods import normalize_ner_method
from basis.domain.knowledge.pipeline.extract_kwargs import (
    semantica_build_kwargs,
    validate_extract_options,
)


def test_semantica_build_kwargs_llm_injects_chat() -> None:
    opts = TextIngestOptions(ner_method="llm", relation_method="llm")
    kw = semantica_build_kwargs(
        opts,
        {"api_key": "sk-test", "model": "gpt-test", "base_url": "https://api.example/v1"},
    )
    assert kw["llm_model"] == "gpt-test"
    assert kw["api_key"] == "sk-test"
    assert kw["base_url"] == "https://api.example/v1"
    assert kw["ner_method"] == "llm"
    assert kw["relation_method"] == "llm"


def test_validate_llm_requires_chat() -> None:
    opts = TextIngestOptions(extract=True, ner_method="llm", relation_method="llm")
    with pytest.raises(AdminError) as exc:
        validate_extract_options(opts, {"api_key": "", "model": ""})
    assert exc.value.code == "chat_not_configured"


def test_validate_llm_requires_per_job_model_when_platform_model_empty() -> None:
    opts = TextIngestOptions(extract=True, ner_method="llm", relation_method="llm")
    with pytest.raises(AdminError) as exc:
        validate_extract_options(opts, {"api_key": "sk-x", "model": ""})
    assert exc.value.code == "extract_model_required"


def test_semantica_build_kwargs_prefers_per_job_llm_model() -> None:
    opts = TextIngestOptions(
        extract=True,
        ner_method="llm",
        relation_method="llm",
        llm_model="gpt-4o",
    )
    kw = semantica_build_kwargs(
        opts,
        {"api_key": "sk-test", "model": "ignored", "base_url": "https://api.example/v1"},
    )
    assert kw["llm_model"] == "gpt-4o"


def test_reject_non_llm_when_extracting() -> None:
    with pytest.raises(AdminError) as exc:
        normalize_ner_method("pattern", extract=True)
    assert exc.value.code == "unsupported_extract_method"
