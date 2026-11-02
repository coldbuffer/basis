from basis.services.graph.reasoning.forward import infer_with_proof_chains, proof_chains_for_run


def test_infer_with_proof_chains_metformin_rule() -> None:
    facts = ["inhibits(Metformin, mTOR)", "causes(mTOR, Neurodegeneration)"]
    rules = [
        "IF inhibits(Metformin, mTOR) AND causes(mTOR, Neurodegeneration) "
        "THEN candidate(Metformin, Alzheimer's)"
    ]
    inferred, proofs = infer_with_proof_chains(facts, rules)
    assert inferred == ["candidate(Metformin, Alzheimer's)"]
    assert len(proofs) == 1
    assert proofs[0].rule == rules[0]
    assert "inhibits(Metformin, mTOR)" in proofs[0].premises
    assert "causes(mTOR, Neurodegeneration)" in proofs[0].premises


def test_proof_chains_for_run_aligns_with_inferred() -> None:
    facts = ["parent(Alice, Bob)"]
    rules = ["IF parent(Alice, Bob) THEN ancestor(Alice, Bob)"]
    chains = proof_chains_for_run(facts, rules, ["ancestor(Alice, Bob)"])
    assert chains[0]["conclusion"] == "ancestor(Alice, Bob)"
    assert chains[0]["rule"] == rules[0]
    assert chains[0]["premises"] == ["parent(Alice, Bob)"]
