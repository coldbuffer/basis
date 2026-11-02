"""run_reasoning defaults facts from typed_facts when omitted."""

import pytest
from fastapi.testclient import TestClient

from basis.services.knowledge.demo.pack_v1 import DEMO_RULE_BODY
from basis.app import create_app
from basis.infra.runtime.config import Settings
from tests.support.demo_workspace import create_workspace_with_demo

pytest.importorskip("semantica")


def test_run_reasoning_without_facts_fails_on_empty_workspace(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "empty@example.com", "password": "password1", "display_name": "E"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=headers,
        json={"rules": [DEMO_RULE_BODY], "apply_to_graph": False},
    )
    assert resp.status_code == 422


def test_run_reasoning_explicit_facts_on_empty_workspace(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "facts@example.com", "password": "password1", "display_name": "F"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=headers,
        json={
            "facts": ["inhibits(Metformin, mTOR)", "causes(mTOR, Neurodegeneration)"],
            "rules": [
                "IF inhibits(Metformin, mTOR) AND causes(mTOR, Neurodegeneration) "
                "THEN candidate(Metformin, Alzheimer's)"
            ],
            "apply_to_graph": False,
        },
    )
    assert resp.status_code == 200
    assert resp.json().get("facts_source") == "request"
