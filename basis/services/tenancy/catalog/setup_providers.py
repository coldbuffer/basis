"""Built-in LLM / embedding providers (aligned with Fellow desktop setup catalog)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModelKind = Literal["llm", "embed"]
ProviderId = str


@dataclass(frozen=True)
class ProviderModelTemplate:
    name: str
    display_name: str
    model: str


@dataclass(frozen=True)
class SetupProvider:
    id: ProviderId
    label: str
    default_api_base: str
    api_base_editable: bool
    api_key_url: str | None
    models: tuple[ProviderModelTemplate, ...]


def _norm_base(api_base: str | None) -> str:
    return (api_base or "").strip().rstrip("/").lower()


LLM_PROVIDERS: tuple[SetupProvider, ...] = (
    SetupProvider(
        id="deepseek",
        label="DeepSeek",
        default_api_base="https://api.deepseek.com",
        api_base_editable=False,
        api_key_url="https://platform.deepseek.com/api_keys",
        models=(
            ProviderModelTemplate("deepseek-chat", "DeepSeek Chat", "deepseek-chat"),
            ProviderModelTemplate("deepseek-reasoner", "DeepSeek Reasoner", "deepseek-reasoner"),
        ),
    ),
    SetupProvider(
        id="openai",
        label="OpenAI",
        default_api_base="https://api.openai.com/v1",
        api_base_editable=False,
        api_key_url="https://platform.openai.com/api-keys",
        models=(
            ProviderModelTemplate("gpt-4o-mini", "GPT-4o mini", "gpt-4o-mini"),
            ProviderModelTemplate("gpt-4o", "GPT-4o", "gpt-4o"),
        ),
    ),
    SetupProvider(
        id="openrouter",
        label="OpenRouter",
        default_api_base="https://openrouter.ai/api/v1",
        api_base_editable=False,
        api_key_url="https://openrouter.ai/keys",
        models=(ProviderModelTemplate("openrouter-auto", "OpenRouter Auto", "openrouter/auto"),),
    ),
    SetupProvider(
        id="zhipu",
        label="Zhipu",
        default_api_base="https://open.bigmodel.cn/api/paas/v4",
        api_base_editable=False,
        api_key_url="https://bigmodel.cn/usercenter/proj-mgmt/apikeys",
        models=(
            ProviderModelTemplate("glm-4-flash", "GLM-4 Flash", "glm-4-flash"),
            ProviderModelTemplate("glm-4-plus", "GLM-4 Plus", "glm-4-plus"),
        ),
    ),
    SetupProvider(
        id="minimax",
        label="MiniMax",
        default_api_base="https://api.minimaxi.com/v1",
        api_base_editable=False,
        api_key_url="https://platform.minimaxi.com/user-center/basic-information/interface-key",
        models=(ProviderModelTemplate("minimax-m2.5", "MiniMax M2.5", "MiniMax-M2.5"),),
    ),
    SetupProvider(
        id="moonshot",
        label="Moonshot",
        default_api_base="https://api.moonshot.cn/v1",
        api_base_editable=False,
        api_key_url="https://platform.moonshot.cn/console/api-keys",
        models=(ProviderModelTemplate("kimi-k2", "Kimi K2", "kimi-k2-0905-preview"),),
    ),
    SetupProvider(
        id="ollama",
        label="Ollama",
        default_api_base="http://127.0.0.1:11434/v1",
        api_base_editable=True,
        api_key_url=None,
        models=(ProviderModelTemplate("llama3", "Llama 3", "llama3"),),
    ),
    SetupProvider(
        id="custom",
        label="Custom",
        default_api_base="",
        api_base_editable=True,
        api_key_url=None,
        models=(ProviderModelTemplate("default", "Default", "default"),),
    ),
)

EMBED_PROVIDERS: tuple[SetupProvider, ...] = (
    SetupProvider(
        id="openai",
        label="OpenAI",
        default_api_base="https://api.openai.com/v1",
        api_base_editable=False,
        api_key_url="https://platform.openai.com/api-keys",
        models=(
            ProviderModelTemplate(
                "text-embedding-3-small",
                "text-embedding-3-small",
                "text-embedding-3-small",
            ),
            ProviderModelTemplate(
                "text-embedding-3-large",
                "text-embedding-3-large",
                "text-embedding-3-large",
            ),
        ),
    ),
    SetupProvider(
        id="zhipu",
        label="Zhipu",
        default_api_base="https://open.bigmodel.cn/api/paas/v4",
        api_base_editable=False,
        api_key_url="https://bigmodel.cn/usercenter/proj-mgmt/apikeys",
        models=(ProviderModelTemplate("embedding-3", "Embedding-3", "embedding-3"),),
    ),
    SetupProvider(
        id="ollama",
        label="Ollama",
        default_api_base="http://127.0.0.1:11434/v1",
        api_base_editable=True,
        api_key_url=None,
        models=(ProviderModelTemplate("nomic-embed-text", "nomic-embed-text", "nomic-embed-text"),),
    ),
    SetupProvider(
        id="custom",
        label="Custom",
        default_api_base="",
        api_base_editable=True,
        api_key_url=None,
        models=(ProviderModelTemplate("default", "Default", "default"),),
    ),
)


def providers_for_kind(kind: ModelKind) -> tuple[SetupProvider, ...]:
    return LLM_PROVIDERS if kind == "llm" else EMBED_PROVIDERS


def get_provider(kind: ModelKind, provider_id: str | None) -> SetupProvider:
    providers = providers_for_kind(kind)
    if provider_id:
        for item in providers:
            if item.id == provider_id:
                return item
    return providers[0]


def infer_provider_id(kind: ModelKind, api_base: str | None, stored_id: str | None) -> str:
    if stored_id:
        for item in providers_for_kind(kind):
            if item.id == stored_id:
                return stored_id
    base = _norm_base(api_base)
    if base:
        for item in providers_for_kind(kind):
            if item.id != "custom" and _norm_base(item.default_api_base) == base:
                return item.id
    return "custom" if base else providers_for_kind(kind)[0].id


def provider_payload(provider: SetupProvider) -> dict:
    return {
        "id": provider.id,
        "label": provider.label,
        "default_api_base": provider.default_api_base,
        "api_base_editable": provider.api_base_editable,
        "api_key_url": provider.api_key_url,
        "models": [
            {"name": m.name, "display_name": m.display_name, "model": m.model}
            for m in provider.models
        ],
    }
