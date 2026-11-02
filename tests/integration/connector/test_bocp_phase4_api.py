"""End-to-end HTTP integration tests for BOCP Phase 4A: /api/v1/workspaces/{workspace_id}/connectors/* and Review writeback approval."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from basis.infra.runtime.config import Settings
from basis.app import create_app


def test_connectors_http_endpoints_and_review_writeback_flow(tmp_path: Path) -> None:
    # 1. Create an external SQLite database acting as the remote ERP database
    ext_db_path = tmp_path / "remote_erp.db"
    ext_engine = create_engine(f"sqlite:///{ext_db_path}")
    with ext_engine.begin() as ext_conn:
        ext_conn.execute(
            text(
                """
                CREATE TABLE accounts (
                    account_id TEXT PRIMARY KEY,
                    account_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        )
        ext_conn.execute(
            text(
                """
                INSERT INTO accounts (account_id, account_name, status, updated_at)
                VALUES ('acc_1', 'Globex Corp', 'trial', '2026-01-01T00:00:00Z')
                """
            )
        )
    ext_engine.dispose()

    # 2. Boot Basis FastAPI app
    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@basis.local",
            "password": "password123",
            "display_name": "Admin",
        },
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    # 3. Query Connector Catalog
    cat_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/catalog",
        headers=headers,
        params={"has_streams_only": True},
    )
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert cat_data["stats"]["providers"] == 4
    services = {c["service"] for c in cat_data["connectors"]}
    assert services == {"github", "mysql", "postgres"}

    # 4. Create Connection & Run CHECK + DISCOVER
    put_conn = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "auth_type": "database_dsn",
            "connection_config": {"dsn": f"sqlite:///{ext_db_path}"},
            "credentials": {"username": "erp_user", "password": "secret"},
        },
    )
    assert put_conn.status_code == 200
    assert put_conn.json()["connection"]["has_credentials"] is True

    chk_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres/check",
        headers=headers,
    )
    assert chk_resp.status_code == 200
    assert chk_resp.json()["ok"] is True

    disc_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres/discover",
        headers=headers,
        params={"external_table": "accounts"},
    )
    assert disc_resp.status_code == 200
    disc_data = disc_resp.json()
    assert disc_data["primary_key"] == ["account_id"]
    assert {f["name"] for f in disc_data["fields"]} == {
        "account_id",
        "account_name",
        "status",
        "updated_at",
    }

    # 5. Create Table Mapping & Execute Inbound Sync
    map_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings",
        headers=headers,
        json={
            "provider": "postgres",
                        "stream_name": "table_records",
            "external_table": "accounts",
            "primary_key_column": "account_id",
            "cursor_column": "updated_at",
            "label_column": "account_name",
            "target_class_uri": "urn:basis:class:Account",
            "column_mappings": [
                {
                    "column": "status",
                    "surface_phrase": "has account status",
                    "predicate_uri": "urn:basis:prop:status",
                    "writable": True,
                }
            ],
            "sync_direction": "bidirectional",
            "writeback_mode": "review",
        },
    )
    assert map_resp.status_code == 200
    mapping_id = map_resp.json()["mapping"]["id"]

    sync_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/{mapping_id}/sync",
        headers=headers,
    )
    assert sync_resp.status_code == 200
    assert sync_resp.json()["added"] == 1

    # Verify graph projection was automatically rebuilt after connector sync
    graph_nodes_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/graph/nodes",
        headers=headers,
    )
    assert graph_nodes_resp.status_code == 200
    node_labels = {
        n.get("label") or (n.get("properties") or {}).get("name")
        for n in graph_nodes_resp.json().get("nodes", [])
    }
    assert "Globex Corp" in node_labels

    # Find synced entity & verify entity facts endpoint returns external_sync context
    find_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/entities/find",
        headers=headers,
        params={"q": "Globex"},
    )
    assert find_resp.status_code == 200
    entity_id = find_resp.json()["ledger_entities"][0]["id"]

    facts_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/entities/{entity_id}/facts",
        headers=headers,
    )
    assert facts_resp.status_code == 200
    ext_sync = facts_resp.json().get("external_sync")
    assert ext_sync is not None
    assert ext_sync["provider"] == "postgres"
    assert ext_sync["external_table"] == "accounts"
    assert ext_sync["external_pk"] == "acc_1"
    assert ext_sync["writable_columns"][0]["column"] == "status"
    assert ext_sync["writable_columns"][0]["current_value"] == "trial"

    # 6. Propose Entity Writeback -> Creates Outbox + Open Review Item
    prop_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/outbox/propose",
        headers=headers,
        json={
            "entity_id": entity_id,
            "field_updates": {"status": "enterprise_active"},
        },
    )
    assert prop_resp.status_code == 200
    outbox = prop_resp.json()["outbox"]
    assert outbox["status"] == "pending_review"
    review_item_id = outbox["review_item_id"]
    assert review_item_id is not None

    # 7. Approve via Standard workspace review endpoint -> Executes Remote Writeback!
    app_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/review/items/{review_item_id}/approve",
        headers=headers,
        json={"rationale": "Approved enterprise upgrade"},
    )
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["item"]["status"] == "approved"
    assert app_data["outbox"]["status"] == "synced"
    assert app_data["decision_id"] is not None

    # Verify remote DB was updated
    ext_engine = create_engine(f"sqlite:///{ext_db_path}")
    with ext_engine.connect() as ext_conn:
        remote_status = ext_conn.execute(
            text("SELECT status FROM accounts WHERE account_id = 'acc_1'")
        ).scalar()
    ext_engine.dispose()
    assert remote_status == "enterprise_active"

    # Verify connector runs log endpoint
    runs_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/runs",
        headers=headers,
    )
    assert runs_resp.status_code == 200
    assert len(runs_resp.json()["runs"]) >= 3

def test_table_mapping_get_update_and_delete(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path / "basis_data")))
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "editor@basis.local",
            "password": "password123",
            "display_name": "Editor",
        },
    )
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/connections/postgres",
        headers=headers,
        json={
            "auth_type": "database_dsn",
            "connection_config": {"dsn": "sqlite:///:memory:"},
            "credentials": {},
        },
    )

    create_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings",
        headers=headers,
        json={
            "provider": "postgres",
                        "stream_name": "table_records",
            "external_table": "demo_items",
            "primary_key_column": "id",
            "label_column": "name",
            "target_class_uri": "urn:basis:class:DemoItem",
            "column_mappings": [],
            "sync_direction": "inbound",
            "writeback_mode": "disabled",
        },
    )
    assert create_resp.status_code == 200
    mapping_id = create_resp.json()["mapping"]["id"]

    get_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/{mapping_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["mapping"]["provider"] == "postgres"
    assert get_resp.json()["mapping"]["external_table"] == "demo_items"

    update_resp = client.put(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/{mapping_id}",
        headers=headers,
        json={
            "provider": "postgres",
                        "stream_name": "table_records",
            "external_table": "demo_items_v2",
            "primary_key_column": "id",
            "label_column": "title",
            "target_class_uri": "urn:basis:class:DemoItem",
            "column_mappings": [],
            "sync_direction": "inbound",
            "writeback_mode": "disabled",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["mapping"]["external_table"] == "demo_items_v2"
    assert update_resp.json()["mapping"]["label_column"] == "title"

    delete_resp = client.delete(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/{mapping_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    missing_resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/connectors/table-mappings/{mapping_id}",
        headers=headers,
    )
    assert missing_resp.status_code == 404
