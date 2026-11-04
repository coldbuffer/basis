"""SQL catalog sources snapshot schema metadata from a live database."""

import sqlite3

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def _client(tmp_path):
    client = TestClient(create_app(Settings(data_dir=tmp_path, ingest_inline=True)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "catalog@example.com", "password": "password1", "display_name": "Catalog"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    return client, headers, workspace_id


def test_sql_catalog_snapshot_reads_schema_not_rows(tmp_path) -> None:
    source = tmp_path / "people.sqlite"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute(
            """
            CREATE TABLE skip_me (
                id INTEGER PRIMARY KEY,
                person_id INTEGER REFERENCES people(id)
            )
            """
        )
        conn.execute("INSERT INTO people (id, name) VALUES (1, 'ada')")
        conn.commit()

    client, headers, workspace_id = _client(tmp_path)
    uri = "sqlite:///" + source.resolve().as_posix()
    created = client.put(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr",
        headers=headers,
        json={
            "display_name": "HR",
            "connection_uri": uri,
            "table_deny_regex": "skip",
        },
    )
    assert created.status_code == 200
    assert created.json()["source"]["scheme"] == "sqlite"
    assert created.json()["source"]["connection_uri"] == uri

    unreachable = client.put(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/warehouse",
        headers=headers,
        json={
            "display_name": "Warehouse",
            "connection_uri": "postgresql://user:s3cret@127.0.0.1:1/demo",
        },
    )
    assert unreachable.status_code == 400
    assert unreachable.json()["detail"]["code"] == "sql_catalog_connect_failed"
    assert "s3cret" not in unreachable.json()["detail"]["message"]

    secret_uri = "sqlite://user:s3cret@" + source.resolve().as_posix()
    secret = client.put(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/warehouse",
        headers=headers,
        json={
            "display_name": "Warehouse",
            "connection_uri": secret_uri,
        },
    )
    assert secret.status_code == 200
    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources",
        headers=headers,
    )
    assert listed.status_code == 200
    warehouse = next(item for item in listed.json()["sources"] if item["source_id"] == "warehouse")
    assert "s3cret" not in warehouse["connection_uri"]
    assert "***" in warehouse["connection_uri"]

    snap = client.post(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr/snapshot",
        headers=headers,
    )
    assert snap.status_code == 200
    body = snap.json()["snapshot"]
    assert body["dialect"] == "sqlite"
    assert body["database_name"] == "people"
    names = {table["table_name"] for table in body["catalog"]["tables"]}
    assert names == {"people"}
    columns = {column["column_name"] for column in body["catalog"]["columns"]}
    assert columns == {"id", "name"}
    assert body["catalog"]["primary_keys"][0]["column_name"] == "id"
    assert body["catalog"]["foreign_keys"] == []
    assert all("ada" not in str(row) for row in body["catalog"]["tables"])

    listed_after = client.get(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources",
        headers=headers,
    )
    hr = next(item for item in listed_after.json()["sources"] if item["source_id"] == "hr")
    assert hr["counts"] == {"tables": 1, "columns": 2}

    stored = client.get(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr/snapshot",
        headers=headers,
    )
    assert stored.status_code == 200
    assert stored.json()["snapshot"]["counts"]["tables"] == 1

    removed = client.delete(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr",
        headers=headers,
    )
    assert removed.status_code == 200
    missing = client.get(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr/snapshot",
        headers=headers,
    )
    assert missing.status_code == 404


def test_sql_catalog_connection_test_does_not_save(tmp_path) -> None:
    source = tmp_path / "people.sqlite"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()

    client, headers, workspace_id = _client(tmp_path)
    uri = "sqlite:///" + source.resolve().as_posix()
    ok = client.post(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/connection-test",
        headers=headers,
        json={"connection_uri": uri},
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True
    listed = client.get(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources",
        headers=headers,
    )
    assert listed.json()["sources"] == []

    missing = client.post(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/connection-test",
        headers=headers,
        json={"connection_uri": "sqlite:///tmp/basis-sql-catalog-missing.sqlite"},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"]["code"] == "sql_catalog_connect_failed"


def test_sql_catalog_snapshot_becomes_ontology(tmp_path) -> None:
    source = tmp_path / "people.sqlite"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute(
            """
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY,
                person_id INTEGER REFERENCES people(id)
            )
            """
        )
        conn.commit()

    client, headers, workspace_id = _client(tmp_path)
    uri = "sqlite:///" + source.resolve().as_posix()
    created = client.put(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr",
        headers=headers,
        json={"display_name": "HR", "connection_uri": uri},
    )
    assert created.status_code == 200
    snap = client.post(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr/snapshot",
        headers=headers,
    )
    assert snap.status_code == 200

    applied = client.post(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr/ontology",
        headers=headers,
    )
    assert applied.status_code == 200
    body = applied.json()
    assert body["classes"] == 2
    assert body["datatype_properties"] == 4
    assert body["object_properties"] == 1
    ontology_uri = body["uri"]

    graph = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/graph",
        headers=headers,
        params={"uri": ontology_uri},
    )
    assert graph.status_code == 200
    nodes = graph.json()["nodes"]
    labels = {node["content"] for node in nodes}
    assert {"people", "notes", "name", "person_id"} <= labels
    kinds = {node["content"]: node["entity_type"] for node in nodes}
    assert kinds["people"] == "class"
    assert kinds["name"] == "property"
    edge_types = {edge["type"] for edge in graph.json()["edges"]}
    assert "rdfs:domain" in edge_types
    assert "rdfs:range" in edge_types

    again = client.post(
        f"/api/v1/workspaces/{workspace_id}/sql-catalog/sources/hr/ontology",
        headers=headers,
    )
    assert again.status_code == 200
    assert again.json()["edges_added"] == 0
    graph_again = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/graph",
        headers=headers,
        params={"uri": ontology_uri},
    )
    class_count = sum(1 for node in graph_again.json()["nodes"] if node["content"] == "people")
    assert class_count == 1
