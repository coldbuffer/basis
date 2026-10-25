"""Derived facts ledger + reasoning persist (F-RUL-03)."""

from pathlib import Path

import pytest

pytest.importorskip("semantica")

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.capabilities import graph_runtime_available
from basis.domain.tenancy.admin.store import AdminStore
from basis.infra.runtime.config import Settings
from basis.domain.knowledge.blob_store import BlobStore
from basis.domain.knowledge.services.derived_facts_service import persist_reasoning_derived
from basis.domain.knowledge.store import KnowledgeStore


def _workspace_id(tmp_path: Path) -> str:
    admin = AdminStore(tmp_path / "basis.db")
    user, _ = admin.register("df@example.com", "password1", "DF")
    workspace = admin.create_workspace(user, "DF KB", None, "restricted")
    admin.close()
    return workspace.id


def _knowledge(tmp_path: Path) -> KnowledgeStore:
    return KnowledgeStore(tmp_path / "basis.db", BlobStore(tmp_path))


def test_insert_and_list_derived_facts(tmp_path) -> None:
    workspace_id = _workspace_id(tmp_path)
    store = _knowledge(tmp_path)
    subj = store.get_or_create_entity_by_label(workspace_id, "Alice")
    obj = store.get_or_create_entity_by_label(workspace_id, "Bob")
    fact_id = store.insert_derived_fact(
        workspace_id,
        subject_id=subj,
        predicate_uri="urn:basis:pred:knows",
        object_entity_id=obj,
        object_value=None,
        rule_id=None,
        derivations=[("ground_fact", "knows(Alice, Bob)")],
    )
    assert fact_id
    listed = store.list_derived_facts(workspace_id)
    assert len(listed) == 1
    assert listed[0]["derivations"][0]["premise_id"] == "knows(Alice, Bob)"


def test_persist_reasoning_derived_from_proof_chains(tmp_path) -> None:
    workspace_id = _workspace_id(tmp_path)
    store = _knowledge(tmp_path)
    chains = [
        {
            "conclusion": "ancestor(Alice, Bob)",
            "rule": "IF parent(Alice, Bob) THEN ancestor(Alice, Bob)",
            "premises": ["parent(Alice, Bob)"],
        }
    ]
    out = persist_reasoning_derived(store, workspace_id, chains)
    assert out["created"] == 1
    assert store.list_derived_facts(workspace_id)


def test_ledger_derived_facts_route(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "df2@example.com", "password": "password1", "display_name": "DF2"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    store = _knowledge(tmp_path)
    subj = store.get_or_create_entity_by_label(workspace_id, "X")
    obj = store.get_or_create_entity_by_label(workspace_id, "Y")
    store.insert_derived_fact(
        workspace_id,
        subject_id=subj,
        predicate_uri="urn:basis:pred:rel",
        object_entity_id=obj,
        object_value=None,
        rule_id=None,
        derivations=[],
    )
    res = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/derived-facts", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["derived_facts"]) >= 1

    other = store.get_or_create_entity_by_label(workspace_id, "ZOnly")
    store.insert_derived_fact(
        workspace_id,
        subject_id=other,
        predicate_uri="urn:basis:pred:only",
        object_entity_id=None,
        object_value="literal",
        rule_id=None,
        derivations=[],
    )
    filtered = client.get(
        f"/api/v1/workspaces/{workspace_id}/ledger/derived-facts?entity_id={subj}",
        headers=headers,
    )
    assert filtered.status_code == 200
    rows = filtered.json()["derived_facts"]
    assert rows
    assert all(r["subject_id"] == subj or r["object_entity_id"] == subj for r in rows)
    assert not any(r["subject_id"] == other and r.get("object_value") == "literal" for r in rows)


def test_entity_facts_includes_derived_facts(tmp_path) -> None:
    workspace_id = _workspace_id(tmp_path)
    store = _knowledge(tmp_path)
    subj = store.get_or_create_entity_by_label(workspace_id, "Subj")
    obj = store.get_or_create_entity_by_label(workspace_id, "Obj")
    store.insert_derived_fact(
        workspace_id,
        subject_id=subj,
        predicate_uri="urn:basis:pred:rel",
        object_entity_id=obj,
        object_value=None,
        rule_id=None,
        derivations=[("ground_fact", "rel(Subj, Obj)")],
    )
    listed = store.list_derived_facts_for_entity(workspace_id, subj)
    assert len(listed) == 1


def test_list_derived_facts_filtered_by_entity(tmp_path) -> None:
    workspace_id = _workspace_id(tmp_path)
    store = _knowledge(tmp_path)
    subj = store.get_or_create_entity_by_label(workspace_id, "OnlySubj")
    other = store.get_or_create_entity_by_label(workspace_id, "OtherEnt")
    store.insert_derived_fact(
        workspace_id,
        subject_id=subj,
        predicate_uri="urn:basis:pred:r",
        object_entity_id=other,
        object_value=None,
        rule_id=None,
        derivations=[],
    )
    store.insert_derived_fact(
        workspace_id,
        subject_id=other,
        predicate_uri="urn:basis:pred:r2",
        object_entity_id=subj,
        object_value=None,
        rule_id=None,
        derivations=[],
    )
    for_subj = store.list_derived_facts_for_entity(workspace_id, subj)
    assert len(for_subj) == 2


def test_reasoning_apply_persists_derived_facts(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ra@example.com", "password": "password1", "display_name": "RA"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]

    run = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=headers,
        json={
            "facts": ["parent(PersistA, PersistB)"],
            "rules": ["IF parent(PersistA, PersistB) THEN ancestor(PersistA, PersistB)"],
            "mode": "forward",
            "apply_to_graph": True,
        },
    )
    assert run.status_code == 200
    body = run.json()
    assert body.get("derived_facts_persisted", {}).get("created", 0) >= 1
    assert isinstance(body.get("projection"), dict)
    assert body["projection"].get("projection_revision") is not None
    listed = client.get(f"/api/v1/workspaces/{workspace_id}/ledger/derived-facts", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["derived_facts"]) >= 1


def test_reasoning_apply_with_chunk_evidence(tmp_path) -> None:
    if not graph_runtime_available():
        pytest.skip("explorer extra not installed")

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "rev@example.com", "password": "password1", "display_name": "REV"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        headers=headers,
        json={
            "doc_id": "reason-evidence",
            "text": "PersistA is parent of PersistB.",
            "wait": True,
            "extract": False,
            "chunk": True,
        },
    )
    search = client.get(
        f"/api/v1/workspaces/{workspace_id}/search",
        headers=headers,
        params={"q": "PersistA", "limit": 1},
    ).json()
    chunk_id = search["chunks"][0].get("chunk_id") or search["chunks"][0].get("id")
    assert chunk_id

    run = client.post(
        f"/api/v1/workspaces/{workspace_id}/reasoning/run",
        headers=headers,
        json={
            "facts": ["parent(PersistA, PersistB)"],
            "rules": ["IF parent(PersistA, PersistB) THEN ancestor(PersistA, PersistB)"],
            "mode": "forward",
            "apply_to_graph": True,
            "chunk_id": chunk_id,
        },
    )
    assert run.status_code == 200
    body = run.json()
    assert body.get("evidence", {}).get("chunk_id") == chunk_id
    assert body.get("added_edges", 0) >= 1


def test_list_ingest_jobs_alias(tmp_path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "ij@example.com", "password": "password1", "display_name": "IJ"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    listed = client.get(f"/api/v1/workspaces/{workspace_id}/ingest/jobs", headers=headers)
    assert listed.status_code == 200
    assert "jobs" in listed.json()
    assert "processing_jobs_path" in listed.json()
