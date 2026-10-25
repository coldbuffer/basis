"""Persisted workspace SHACL used by shapes list and conflict scan."""

from pathlib import Path

from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app
from fastapi.testclient import TestClient


def test_governance_shacl_put_and_shapes_list(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "shacl@example.com", "password": "password1", "display_name": "S"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    ontology_uri = "http://example.org/onto/demo"
    turtle = (
        "@prefix sh: <http://www.w3.org/ns/shacl#> .\n"
        "@prefix ex: <http://example.org/> .\n"
        "ex:Shape a sh:NodeShape ; sh:targetClass ex:Thing .\n"
    )
    put = client.put(
        f"/api/v1/workspaces/{workspace_id}/governance/shacl",
        headers=headers,
        json={"ontology_uri": ontology_uri, "shacl_turtle": turtle},
    )
    assert put.status_code == 200
    assert put.json()["config"]["governance_ontology_uri"] == ontology_uri
    assert "ex:Shape" in (put.json()["config"]["governance_shacl_turtle"] or "")

    get = client.get(f"/api/v1/workspaces/{workspace_id}/governance/config", headers=headers)
    assert get.status_code == 200
    cfg = get.json()["config"]
    assert cfg["governance_ontology_uri"] == ontology_uri
    assert "ex:Shape" in (cfg.get("governance_shacl_turtle") or "")
