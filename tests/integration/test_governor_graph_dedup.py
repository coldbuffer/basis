"""Graph semantic dedup in governor run (F-GOV-04 Phase D)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from basis.domain.knowledge.services.governor_cluster import ENTITY_CLUSTER_KIND
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.infra.runtime.config import Settings
from basis.interface.http.app import create_app


def test_governor_run_returns_graph_dedup_section(tmp_path: Path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "gd@example.com", "password": "password1", "display_name": "GD"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={
            "doc_id": "gd1",
            "text": "Alice knows Bob. Alice works with Bob.",
            "wait": True,
            "extract": True,
        },
    )

    dedup = client.post(
        f"/api/v1/workspaces/{workspace_id}/enrich/dedup",
        headers=headers,
        json={"threshold": 0.5},
    )
    assert dedup.status_code == 200
    flagged = int(dedup.json().get("total_flagged") or 0)

    run = client.post(
        f"/api/v1/workspaces/{workspace_id}/governance/governor/run",
        headers=headers,
        json={
            "dedup_threshold": 0.5,
            "include_shacl": False,
            "include_low_confidence": False,
            "include_entity_label_clusters": False,
            "include_graph_dedup": True,
        },
    )
    assert run.status_code == 200
    body = run.json()
    assert "graph_dedup_clusters" in body
    assert body.get("dedup_threshold") == 0.5
    graph_section = body["graph_dedup_clusters"]
    assert "created" in graph_section
    if flagged > 0:
        assert graph_section.get("created", 0) >= 1
        items = client.get(
            f"/api/v1/workspaces/{workspace_id}/review/items",
            headers=headers,
            params={"kind": ENTITY_CLUSTER_KIND},
        ).json()["items"]
        sources = [item.get("payload", {}).get("source") for item in items]
        assert "graph_semantic_dedup" in sources
