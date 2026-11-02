from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _pg_client(tmp_path: Path, postgres_url: str) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path, database_url=postgres_url)))


def _register_headers(client: TestClient, email: str) -> tuple[dict[str, str], str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password1", "display_name": email.split("@")[0]},
    )
    assert registered.status_code == 200
    headers = {"Authorization": f"Bearer {registered.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return headers, workspace_id


@pytest.mark.integration
def test_postgres_ledger_fts_pgvector_and_mcp(
    tmp_path: Path, postgres_url: str
) -> None:
    client = _pg_client(tmp_path, postgres_url)
    headers, workspace_id = _register_headers(client, "pg@example.com")

    config = client.get(f"/api/v1/workspaces/{workspace_id}/search/config", headers=headers).json()
    assert config["config"]["chunk_backend"] == "postgres_ledger"
    assert config["config"]["vector_backend"] == "pgvector"

    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files={
            "file": (
                "postgres.txt",
                b"PostgreSQL hybrid retrieval supports concurrent MCP clients.",
                "text/plain",
            )
        },
        data={"extract": "false", "wait": "true"},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["embed_indexed"] == 1

    searched = client.get(
        f"/api/v1/workspaces/{workspace_id}/search",
        headers=headers,
        params={"q": "hybrid retrieval"},
    )
    assert searched.status_code == 200
    assert searched.json()["mode"] == "hybrid"
    assert searched.json()["chunks"]

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_chunks",
            "arguments": {"query": "PostgreSQL", "limit": 5},
        },
    }
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    f"/api/v1/workspaces/{workspace_id}/mcp", headers=headers, json=payload
                ),
                range(16),
            )
        )
    assert all(response.status_code == 200 for response in responses)
    client.close()


@pytest.mark.integration
def test_postgres_workspace_graph_audit_list(tmp_path: Path, postgres_url: str) -> None:
    client = _pg_client(tmp_path, postgres_url)
    headers, workspace_id = _register_headers(client, "audit@example.com")
    audit = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/graph-mutations",
        headers=headers,
    )
    assert audit.status_code == 200
    assert "events" in audit.json()
    client.close()


@pytest.mark.integration
def test_postgres_platform_audit_and_workspace_api_tokens(tmp_path: Path, postgres_url: str) -> None:
    client = _pg_client(tmp_path, postgres_url)
    headers, workspace_id = _register_headers(client, "pg-tokens@example.com")

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/tokens",
        headers=headers,
        json={
            "name": "pg-read",
            "scope": "read",
            "http_allowed_operations": ["graph_stats"],
        },
    )
    assert created.status_code == 200
    secret = created.json()["secret"]
    api_headers = {"Authorization": f"Bearer {secret}"}
    assert (
        client.get(f"/api/v1/workspaces/{workspace_id}/graph/stats", headers=api_headers).status_code
        == 200
    )

    platform_audit = client.get("/api/v1/audit", headers=headers, params={"limit": 10})
    assert platform_audit.status_code == 200
    assert isinstance(platform_audit.json()["events"], list)

    client.close()
