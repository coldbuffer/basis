"""Deterministic semantica GraphBuilder.build stub for tests and Playwright E2E."""

from __future__ import annotations

from typing import Any, Callable

PLAYWRIGHT_E2E_CHAT_LLM: dict[str, str] = {
    "api_key": "sk-e2e-playwright",
    "model": "gpt-e2e",
    "base_url": "https://example.test/v1",
}


def graph_builder_stub_build(
    orig: Callable[..., Any],
    sources: Any,
    second_arg: Any = None,
    pipeline_id: Any = None,
    **options: Any,
) -> dict[str, Any]:
    """Deterministic extract output without live LLM calls."""
    if options.get("ner_method") != "llm" and options.get("relation_method") != "llm":
        return orig(sources, second_arg, pipeline_id=pipeline_id, **options)
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
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
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
    if not entities and text.strip():
        token = text.strip().split()[0]
        if token:
            entities.append({"name": token, "type": "TOPIC", "id": token})
    return {"entities": entities, "relationships": relationships, "metadata": {}}
