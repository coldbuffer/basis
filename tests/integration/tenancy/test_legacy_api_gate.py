"""R6: optional legacy /api/* disable."""

from fastapi.testclient import TestClient

from basis.app import create_app
from basis.infra.runtime.config import Settings


def test_legacy_api_blocked_when_disabled(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, legacy_api_enabled=False)
    client = TestClient(create_app(settings))
    assert client.get("/health").status_code == 200
    assert client.get("/api/workspaces").status_code == 410
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "v1only@example.com", "password": "password1", "display_name": "V"},
    )
    assert reg.status_code == 200
