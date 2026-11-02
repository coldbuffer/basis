"""Typed facts → reasoning ground fact strings (demo pack)."""

import pytest
from fastapi.testclient import TestClient

from basis.services.knowledge.services.reasoning_ground_facts import ground_fact_strings_from_typed_facts
from basis.services.knowledge.demo.pack_v1 import DEMO_INFERRED_CONCLUSION, DEMO_RULE_BODY
from basis.services.graph.reasoning.forward import infer_with_proof_chains
from basis.app import create_app
from basis.infra.runtime.config import Settings
from tests.support.demo_workspace import create_workspace_with_demo

pytest.importorskip("semantica")


def test_demo_ground_facts_from_typed_facts(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, ingest_inline=True, demo_workspace_enabled=True)
    app = create_app(settings)
    client = TestClient(app)
    admin = client.post(
        "/api/v1/auth/register",
        json={"email": "gf@example.com", "password": "password1", "display_name": "G"},
    ).json()
    headers = {"Authorization": f"Bearer {admin['token']}"}
    workspace_id = create_workspace_with_demo(client, headers)

    knowledge = app.state.knowledge_store
    facts = ground_fact_strings_from_typed_facts(knowledge, workspace_id)
    assert any(f.startswith("activeAgreement(") for f in facts)
    assert any(f.startswith("commercialContact(") for f in facts)

    _, proofs = infer_with_proof_chains(facts, [DEMO_RULE_BODY])
    assert proofs
    conclusions = {p.conclusion for p in proofs}
    assert DEMO_INFERRED_CONCLUSION in conclusions
