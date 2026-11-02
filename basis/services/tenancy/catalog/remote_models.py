"""OpenAI-compatible remote model listing for admin model setup."""

from __future__ import annotations

import re
from typing import Any, Literal

ModelKind = Literal["llm", "embed"]

CHAT_ENDPOINT_SUFFIX_RE = re.compile(
    r"/(?:chat/completions|completions|messages|responses)/?$",
    re.IGNORECASE,
)

NON_LLM_MODEL_RE = re.compile(
    r"(?:^|[/_.-])(?:embed(?:ding)?s?|embo|bge|m3e|gte|rerank(?:er)?|whisper|tts|"
    r"t2a|t2i|t2v|i2v|speech|music|voice(?:-?clone)?|asr|stt|dall-?e|cogview|cogvideo|"
    r"flux|sdxl|stable-?diffusion|sora|veo|kling|runway|hailuo|moderation|realtime|"
    r"transcribe|gpt-image|image(?:-?gen(?:eration)?)?|video|tokenizer|clip|babbage|"
    r"davinci|curie|ada|text-embedding|text-moderation|omni-moderation|computer-use)"
    r"(?:$|[/_.-])",
    re.IGNORECASE,
)

EMBED_MODEL_RE = re.compile(
    r"(?:^|[/_.-])(?:embed(?:ding)?s?|embo|bge|m3e|gte|text-embedding)(?:$|[/_.-])|"
    r"embedding|nomic-embed",
    re.IGNORECASE,
)


def normalize_openai_api_base(api_base: str) -> str:
    base = api_base.strip().rstrip("/")
    base = CHAT_ENDPOINT_SUFFIX_RE.sub("", base)
    return base.rstrip("/")


def is_printable_ascii(value: str) -> bool:
    return bool(re.fullmatch(r"[\x20-\x7e]*", value))


def is_likely_llm_model(model_id: str) -> bool:
    id_ = model_id.strip()
    if not id_:
        return False
    if re.search(
        r"embedding|whisper|tts-|speech-|music-|cogview|cogvideo|dall-?e|gpt-image|"
        r"text-embedding|moderation|rerank|embo-",
        id_,
        re.IGNORECASE,
    ):
        return False
    return not NON_LLM_MODEL_RE.search(id_)


def is_likely_embed_model(model_id: str) -> bool:
    id_ = model_id.strip()
    if not id_:
        return False
    return bool(EMBED_MODEL_RE.search(id_))


def _title_from_id(model_id: str) -> str:
    base = model_id.split("/")[-1] if model_id else model_id
    parts = re.split(r"[-_]", base)
    return " ".join(p[:1].upper() + p[1:] for p in parts if p)


def fetch_remote_models(
    *,
    api_key: str,
    api_base: str,
    kind: ModelKind,
) -> dict[str, Any]:
    key = api_key.strip()
    base_lower = api_base.strip().lower()
    is_local = "127.0.0.1" in base_lower or "localhost" in base_lower
    if not key and not is_local:
        return {"ok": False, "error": "api_key_required"}
    if key and not is_printable_ascii(key):
        return {"ok": False, "error": "api_key_invalid"}

    base = normalize_openai_api_base(api_base)
    if not base:
        return {"ok": False, "error": "api_base_required"}

    try:
        from openai import OpenAI
    except ImportError:
        return {"ok": False, "error": "openai_missing"}

    client = OpenAI(api_key=key or "ollama", base_url=base)
    try:
        page = client.models.list()
    except Exception as exc:  # noqa: BLE001 — surface message to admin UI
        return {"ok": False, "error": str(exc) or "fetch_failed"}

    raw_ids: list[str] = []
    for item in page.data:
        mid = getattr(item, "id", None) or ""
        if isinstance(mid, str) and mid.strip():
            raw_ids.append(mid.strip())

    filter_fn = is_likely_embed_model if kind == "embed" else is_likely_llm_model
    filtered = [mid for mid in raw_ids if filter_fn(mid)]
    if kind == "llm" and not filtered:
        filtered = [mid for mid in raw_ids if mid.strip()]

    models = [
        {
            "id": mid,
            "name": mid.split("/")[-1].lower().replace(".", "-"),
            "display_name": _title_from_id(mid),
        }
        for mid in sorted(set(filtered), key=str.lower)
    ]
    if not models:
        return {"ok": False, "error": "models_empty"}

    return {"ok": True, "models": models, "source": "remote"}
