from basis.services.graph.sparql.read import sparql_query_preflight


def test_sparql_rejects_update_keyword() -> None:
    out = sparql_query_preflight("DROP ALL")
    assert out is not None
    assert out["error"]
    assert out["rows"] == []


def test_sparql_accepts_select() -> None:
    assert sparql_query_preflight("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1") is None
