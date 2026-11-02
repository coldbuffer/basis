"""Chunk embedding via OpenAI-compatible APIs or local fallback."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

_BATCH = 64


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_texts(texts: list[str], settings: dict[str, str | None]) -> tuple[np.ndarray, str]:
    """Return (vectors shape N x D, model_ref)."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32), "none"

    api_key = (settings.get("api_key") or "").strip()
    model = (settings.get("model") or "").strip()
    base_url = (settings.get("base_url") or "").strip() or None

    if api_key and model:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        model_ref = f"openai-compat:{settings.get('id') or model}"
        rows: list[list[float]] = []
        for start in range(0, len(texts), _BATCH):
            batch = texts[start : start + _BATCH]
            response = client.embeddings.create(model=model, input=batch)
            rows.extend(item.embedding for item in response.data)
        arr = np.asarray(rows, dtype=np.float32)
        return arr, model_ref

    from semantica.embeddings.methods import embed_text

    vecs = embed_text(texts, method="fallback")
    if vecs.ndim == 1:
        vecs = vecs.reshape(1, -1)
    return np.asarray(vecs, dtype=np.float32), "semantica:fallback"


def embed_query(query: str, settings: dict[str, str | None]) -> tuple[np.ndarray, str]:
    vecs, model_ref = embed_texts([query], settings)
    if len(vecs) == 0:
        raise ValueError("empty query")
    return vecs[0], model_ref
