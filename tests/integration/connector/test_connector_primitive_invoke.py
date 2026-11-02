"""BOCP primitive dispatch against real PostgreSQL and GitHub (see ``tests/test.yaml``)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from basis.services.connector import ConnectorAuthVault, ConnectorRuntime
from basis.services.connector.primitive_invoke import execute_connector_primitive
from basis.infra.runtime.config import Settings
from basis.app import create_app
from tests.support.connector_integration import (
    drop_postgres_table,
    postgres_connection_payload,
    seed_postgres_items_table,
    setup_workspace_sqlite,
    unique_pg_table_name,
)


@pytest.mark.integration
def test_github_issues_list_and_create_via_primitive(
    tmp_path: Path, github_integration: dict[str, str]
) -> None:
    owner = github_integration["owner"]
    repo = github_integration["repo"]
    conn = setup_workspace_sqlite(tmp_path)
    try:
        vault = ConnectorAuthVault(conn, vault_secret="test-secret")
        vault.upsert_connection(
            "ws1",
            "github",
            auth_type="api_key",
            credentials={"personal_access_token": github_integration["token"]},
        )
        runtime = ConnectorRuntime(conn, vault_secret="test-secret")

        listed = execute_connector_primitive(
            runtime,
            "ws1",
            "github",
            action_id="issues",
            primitive="list",
            action_params={"owner": owner, "repo": repo},
            limit=10,
        )
        assert isinstance(listed["records"], list)

        title = f"bocp integration {uuid.uuid4().hex[:8]}"
        try:
            created = execute_connector_primitive(
                runtime,
                "ws1",
                "github",
                action_id="issues",
                primitive="mutate",
                operation="create",
                action_params={"owner": owner, "repo": repo},
                changes={"title": title},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                pytest.skip(
                    "PAT cannot create issues on this repo; grant Issues read/write "
                    "(fine-grained) or repo scope (classic)"
                )
            raise
        assert created["result"]["title"] == title
        assert created["result"]["number"] >= 1
    finally:
        conn.close()


@pytest.mark.integration
def test_mcp_invoke_connector_primitive_sql_list(
    tmp_path: Path, postgres_sql_target_url: str
) -> None:
    table = unique_pg_table_name()
    seed_postgres_items_table(postgres_sql_target_url, table_name=table)
    try:
        client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data")))
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "prim@mcp.example.com",
                "password": "password1",
                "display_name": "Prim",
            },
        ).json()
        headers = {"Authorization": f"Bearer {reg['token']}"}
        workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

        client.put(
            f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
            headers=headers,
            json=postgres_connection_payload(postgres_sql_target_url),
        )

        mcp_resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "invoke_connector_primitive",
                    "arguments": {
                        "service": "postgres",
                                                "action_id": "table_records",
                        "primitive": "list",
                        "external_table": table,
                        "limit": 50,
                    },
                },
            },
        )
        assert mcp_resp.status_code == 200
        body = mcp_resp.json()
        assert body["result"]["isError"] is False
        payload = json.loads(body["result"]["content"][0]["text"])
        assert len(payload["records"]) == 1
        assert payload["records"][0]["id"] == "i1"
    finally:
        drop_postgres_table(postgres_sql_target_url, table)


@pytest.mark.integration
def test_github_get_authenticated_user_invoke(
    tmp_path: Path, github_integration: dict[str, str]
) -> None:
    conn = setup_workspace_sqlite(tmp_path)
    try:
        vault = ConnectorAuthVault(conn, vault_secret="test-secret")
        vault.upsert_connection(
            "ws1",
            "github",
            auth_type="api_key",
            credentials={"personal_access_token": github_integration["token"]},
        )
        runtime = ConnectorRuntime(conn, vault_secret="test-secret")

        out = execute_connector_primitive(
            runtime,
            "ws1",
            "github",
            action_id="get_authenticated_user",
            primitive="invoke",
            arguments={},
        )
        assert out["mode"] != "disabled"
        assert out["result"]["login"]
        assert out["result"]["id"]
    finally:
        conn.close()


@pytest.mark.integration
def test_list_reports_has_more_when_limit_truncates(
    tmp_path: Path, github_integration: dict[str, str]
) -> None:
    conn = setup_workspace_sqlite(tmp_path)
    try:
        vault = ConnectorAuthVault(conn, vault_secret="test-secret")
        vault.upsert_connection(
            "ws1",
            "github",
            auth_type="api_key",
            credentials={"personal_access_token": github_integration["token"]},
        )
        runtime = ConnectorRuntime(conn, vault_secret="test-secret")

        listed = execute_connector_primitive(
            runtime,
            "ws1",
            "github",
            action_id="repositories",
            primitive="list",
            limit=1,
        )
        assert len(listed["records"]) == 1
        if listed.get("has_more") is not True:
            pytest.skip(
                "GitHub account has at most one repository; cannot assert has_more"
            )
    finally:
        conn.close()


@pytest.mark.integration
def test_http_invoke_primitive_list(tmp_path: Path, postgres_sql_target_url: str) -> None:
    table = unique_pg_table_name()
    seed_postgres_items_table(postgres_sql_target_url, table_name=table)
    try:
        client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data2")))
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "email": "http-prim@example.com",
                "password": "password1",
                "display_name": "H",
            },
        ).json()
        headers = {"Authorization": f"Bearer {reg['token']}"}
        workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
        client.put(
            f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
            headers=headers,
            json=postgres_connection_payload(postgres_sql_target_url),
        )
        resp = client.post(
            f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres/invoke-primitive",
            headers=headers,
            json={
                "action_id": "table_records",
                "primitive": "list",
                "external_table": table,
                "limit": 10,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["records"][0]["name"] == "One"
    finally:
        drop_postgres_table(postgres_sql_target_url, table)
