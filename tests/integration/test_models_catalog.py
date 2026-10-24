from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings


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


def test_model_catalog_crud(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "admin@example.com")
    headers = _auth(admin["token"])

    empty = client.get("/api/v1/models?kind=llm", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["models"] == []

    created = client.post(
        "/api/v1/models",
        headers=headers,
        json={
            "kind": "llm",
            "provider": "openai",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "api_key": "sk-test-key",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["model"]
    assert body["model"] == "gpt-4o-mini"
    assert body["configured"] is True
    model_id = body["id"]

    listed = client.get("/api/v1/models?kind=llm", headers=headers).json()["models"]
    assert len(listed) == 1

    settings = client.get("/api/v1/settings", headers=headers).json()
    assert settings["chat_model"] == "gpt-4o-mini"
    assert settings["has_chat_key"] is True

    client.delete(f"/api/v1/models/{model_id}", headers=headers)
    assert client.get("/api/v1/models?kind=llm", headers=headers).json()["models"] == []


def test_model_catalog_batch_add(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "batch@example.com")
    headers = _auth(admin["token"])

    created = client.post(
        "/api/v1/models/batch",
        headers=headers,
        json={
            "kind": "llm",
            "provider": "openai",
            "api_base": "https://api.openai.com/v1",
            "models": ["gpt-4o-mini", "gpt-4o", "gpt-4o-mini"],
            "api_key": "sk-batch",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert len(body["models"]) == 2
    assert body["skipped"] == []
    models = {m["model"] for m in body["models"]}
    assert models == {"gpt-4o-mini", "gpt-4o"}

    listed = client.get("/api/v1/models?kind=llm", headers=headers).json()["models"]
    assert len(listed) == 2

    dup = client.post(
        "/api/v1/models/batch",
        headers=headers,
        json={
            "kind": "llm",
            "provider": "openai",
            "api_base": "https://api.openai.com/v1",
            "models": ["gpt-4o"],
            "api_key": "",
        },
    )
    assert dup.status_code == 409


def test_model_endpoint_upsert_credentials_only(tmp_path) -> None:
    client = _client(tmp_path)
    admin = _register(client, "endpoint@example.com")
    headers = _auth(admin["token"])

    saved = client.put(
        "/api/v1/models/endpoint",
        headers=headers,
        json={
            "kind": "llm",
            "provider": "openai",
            "api_base": "https://api.openai.com/v1",
            "api_key": "sk-endpoint",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()["model"]
    assert body["model"] == ""
    assert body["configured"] is True

    listed = client.get("/api/v1/models?kind=llm", headers=headers).json()["models"]
    assert len(listed) == 1

    rotated = client.put(
        "/api/v1/models/endpoint",
        headers=headers,
        json={
            "kind": "llm",
            "provider": "openai",
            "api_base": "https://api.openai.com/v1",
            "api_key": "",
        },
    )
    assert rotated.status_code == 200
    assert rotated.json()["model"]["configured"] is True

    second = client.put(
        "/api/v1/models/endpoint",
        headers=headers,
        json={
            "kind": "llm",
            "provider": "deepseek",
            "api_base": "https://api.deepseek.com",
            "api_key": "sk-deepseek",
        },
    )
    assert second.status_code == 200
    listed = client.get("/api/v1/models?kind=llm", headers=headers).json()["models"]
    assert len(listed) == 2
    providers = {row["provider"] for row in listed}
    assert providers == {"openai", "deepseek"}
