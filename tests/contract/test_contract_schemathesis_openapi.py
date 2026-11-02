"""R2: OpenAPI document loads in Schemathesis (contract harness)."""

import schemathesis
from fastapi.testclient import TestClient

from basis.app import create_app
from basis.http.openapi.spec import openapi_v1_full
from basis.infra.runtime.config import Settings


def test_schemathesis_loads_openapi_v1() -> None:
    schema = schemathesis.openapi.from_dict(openapi_v1_full())
    assert schema.raw_schema["openapi"].startswith("3.")


def test_health_matches_openapi_get(tmp_path) -> None:
    schema = schemathesis.openapi.from_dict(openapi_v1_full())
    assert "/api/v1/health" in schema.raw_schema["paths"]
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
