"""Workspace-scoped vocabulary and ontology alignment routes."""

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings


def test_vocabulary_schemes_empty_graph(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "voc@example.com", "password": "password1", "display_name": "Voc"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    response = client.get(f"/api/v1/workspaces/{workspace_id}/vocabulary/schemes", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_alignments_isolated_between_workspaces(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ali@example.com", "password": "password1", "display_name": "Ali"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_a = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    workspace_b = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Other", "visibility": "restricted"},
    ).json()["id"]

    payload = {
        "source_uri": "http://example.org/a#Class1",
        "target_uri": "http://example.org/b#Class2",
        "relation": "skos:exactMatch",
        "confidence": 0.9,
    }
    created = client.post(f"/api/v1/workspaces/{workspace_a}/ontology/alignments", headers=headers, json=payload)
    assert created.status_code == 200
    alignment_id = created.json()["id"]

    list_a = client.get(f"/api/v1/workspaces/{workspace_a}/ontology/alignments", headers=headers)
    assert list_a.status_code == 200
    assert len(list_a.json()) == 1
    assert list_a.json()[0]["id"] == alignment_id

    list_b = client.get(f"/api/v1/workspaces/{workspace_b}/ontology/alignments", headers=headers)
    assert list_b.status_code == 200
    assert list_b.json() == []


def test_drafts_isolated_between_workspaces(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "dft@example.com", "password": "password1", "display_name": "Dft"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_a = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    workspace_b = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Other", "visibility": "restricted"},
    ).json()["id"]

    ontology_uri = "http://example.org/a/ontology"
    empty_diff = {
        "added_classes": [],
        "removed_classes": [],
        "modified_classes": {},
        "added_properties": [],
        "removed_properties": [],
        "modified_properties": {},
        "added_individuals": [],
        "removed_individuals": [],
        "added_edges": [],
        "removed_edges": [],
        "added_restrictions": [],
        "removed_restrictions": [],
        "added_axioms": [],
        "removed_axioms": [],
        "annotation_changes": {},
    }
    saved = client.patch(
        f"/api/v1/workspaces/{workspace_a}/ontology/draft",
        headers=headers,
        json={
            "ontology_uri": ontology_uri,
            "diff": empty_diff,
            "author": "dft@example.com",
            "summary": "workspace a draft",
        },
    )
    assert saved.status_code == 200
    draft_id = saved.json()["draft_id"]

    list_a = client.get(
        f"/api/v1/workspaces/{workspace_a}/ontology/drafts/{ontology_uri}",
        headers=headers,
    )
    assert list_a.status_code == 200
    assert len(list_a.json()) == 1
    assert list_a.json()[0]["draft_id"] == draft_id

    list_b = client.get(
        f"/api/v1/workspaces/{workspace_b}/ontology/drafts/{ontology_uri}",
        headers=headers,
    )
    assert list_b.status_code == 200
    assert list_b.json() == []


def test_ontology_registry_persisted_across_app_restart(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    settings = Settings(data_dir=tmp_path)
    client = TestClient(create_app(settings))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "per@example.com", "password": "password1", "display_name": "Per"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology",
        headers=headers,
        json={"name": "Persisted", "namespace": "http://example.org/persist"},
    )
    assert created.status_code == 200
    uri = created.json()["uri"]

    client2 = TestClient(create_app(settings))
    admin2 = client2.post(
        "/api/v1/auth/login",
        json={"email": "per@example.com", "password": "password1"},
    ).json()
    headers2 = {"Authorization": f"Bearer {admin2['token']}"}
    reg = client2.get(f"/api/v1/workspaces/{workspace_id}/ontology/registry", headers=headers2)
    assert reg.status_code == 200
    by_uri = {entry.get("uri"): entry for entry in reg.json()}
    assert uri in by_uri
    assert by_uri[uri].get("name") == "Persisted"
    assert by_uri[uri].get("status") == "draft"


def test_ontology_graph_requires_uri(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ogr@example.com", "password": "password1", "display_name": "Ogr"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    missing = client.get(f"/api/v1/workspaces/{workspace_id}/ontology/graph", headers=headers)
    assert missing.status_code == 422

    client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology",
        headers=headers,
        json={"name": "Demo", "namespace": "http://example.org/demo"},
    )
    graph = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/graph",
        headers=headers,
        params={"uri": "http://example.org/demo#ontology"},
    )
    assert graph.status_code == 200
    assert graph.json()["uri"] == "http://example.org/demo#ontology"

    audit = client.get(
        f"/api/v1/workspaces/{workspace_id}/audit/graph-mutations",
        headers=headers,
        params={"action_prefix": "workspace.graph.ontology"},
    )
    assert audit.status_code == 200
    actions = {e["action"] for e in audit.json()["events"]}
    assert "workspace.graph.ontology_create" in actions


def test_ontology_health_after_create(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "hlth@example.com", "password": "password1", "display_name": "Hlth"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    namespace = "http://example.org/health-http"
    created = client.post(
        f"/api/v1/workspaces/{workspace_id}/ontology",
        headers=headers,
        json={"name": "Health HTTP", "namespace": namespace},
    )
    assert created.status_code == 200
    uri = created.json()["uri"]

    health = client.get(
        f"/api/v1/workspaces/{workspace_id}/ontology/health",
        headers=headers,
        params={"uri": uri},
    )
    assert health.status_code == 200
    body = health.json()
    assert body["uri"] == uri
    assert body["name"] == "Health HTTP"
    assert "total_score" in body
    assert any(dim.get("key") == "shacl" for dim in body.get("dimensions", []))
