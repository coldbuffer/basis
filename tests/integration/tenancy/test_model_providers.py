from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings
from basis.services.tenancy.catalog.setup_providers import infer_provider_id, providers_for_kind


def _client(tmp_path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: TestClient, email: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": "管理员"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_list_llm_providers_shape(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "admin@example.com")
    res = client.get("/api/v1/model-providers?kind=llm", headers=_auth(admin["token"]))
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "llm"
    ids = {p["id"] for p in body["providers"]}
    assert "deepseek" in ids
    assert "custom" in ids
    first = body["providers"][0]
    assert "default_api_base" in first
    assert "models" in first and len(first["models"]) >= 1


def test_infer_provider_from_base() -> None:
    assert infer_provider_id("llm", "https://api.openai.com/v1", None) == "openai"
    assert infer_provider_id("llm", "https://example.com/v1", None) == "custom"
    assert infer_provider_id("embed", "https://api.openai.com/v1", "openai") == "openai"


def test_embed_providers_distinct() -> None:
    llm_ids = {p.id for p in providers_for_kind("llm")}
    embed_ids = {p.id for p in providers_for_kind("embed")}
    assert "deepseek" in llm_ids
    assert "deepseek" not in embed_ids
