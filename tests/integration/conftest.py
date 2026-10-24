"""Shared integration fixtures."""

from __future__ import annotations

import pytest

from basis.domain.tenancy.admin.store import AdminStore

_TEST_CHAT = {
    "api_key": "sk-test",
    "model": "gpt-test",
    "base_url": "https://example.test/v1",
}


@pytest.fixture(autouse=True)
def _integration_chat_llm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AdminStore, "get_chat_llm_settings", lambda self: dict(_TEST_CHAT))


@pytest.fixture(autouse=True)
def _stub_llm_graph_builder_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid live LLM calls when jobs use ner/relation method ``llm``."""
    try:
        from semantica.kg import GraphBuilder
    except ImportError:
        return

    def _stub_build(
        self,
        sources,
        second_arg=None,
        pipeline_id=None,
        **options,
    ):
        if options.get("ner_method") != "llm" and options.get("relation_method") != "llm":
            return _orig(self, sources, second_arg, pipeline_id=pipeline_id, **options)
        text = sources
        if isinstance(text, list):
            text = " ".join(
                part if isinstance(part, str) else str(part.get("text", ""))
                for part in text
                if part
            )
        elif isinstance(text, dict):
            text = str(text.get("text", ""))
        else:
            text = str(text or "")
        entities: list[dict] = []
        relationships: list[dict] = []
        if "Alice" in text:
            entities.extend(
                [
                    {"name": "Alice", "type": "PERSON", "id": "Alice"},
                    {"name": "Bob", "type": "PERSON", "id": "Bob"},
                ]
            )
            relationships.append(
                {"source": "Alice", "target": "Bob", "type": "knows", "predicate": "knows"}
            )
        if "Carol" in text:
            entities.append({"name": "Carol", "type": "PERSON", "id": "Carol"})
        if "Dave" in text:
            entities.append({"name": "Dave", "type": "PERSON", "id": "Dave"})
        if "Kim" in text:
            entities.append({"name": "Kim", "type": "PERSON", "id": "Kim"})
        if "Lou" in text:
            entities.append({"name": "Lou", "type": "PERSON", "id": "Lou"})
        if "Ivy" in text:
            entities.append({"name": "Ivy", "type": "PERSON", "id": "Ivy"})
        if "Jake" in text:
            entities.append({"name": "Jake", "type": "PERSON", "id": "Jake"})
        return {"entities": entities, "relationships": relationships, "metadata": {}}

    _orig = GraphBuilder.build
    monkeypatch.setattr(GraphBuilder, "build", _stub_build)
