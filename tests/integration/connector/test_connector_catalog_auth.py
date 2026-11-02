from basis.services.connector.synthesis.connector_catalog_auth import (
    auth_specs_from_connector_app,
)


def test_github_catalog_oauth2_and_pat() -> None:
    app = {
        "auth": [
            {
                "type": "oauth2",
                "authorizationUrl": "https://github.com/login/oauth/authorize",
                "tokenUrl": "https://github.com/login/oauth/access_token",
                "scopes": ["repo"],
                "tokenEndpointAuthMethod": "client_secret_post",
            },
            {
                "type": "api_key",
                "label": "Personal access token",
            },
        ]
    }
    specs = auth_specs_from_connector_app(app, service="github")
    assert len(specs) == 2
    assert specs[0].auth_mode == "oauth2"
    assert specs[0].oauth2 is not None
    assert specs[0].oauth2.authorization_url.endswith("/authorize")
    assert specs[1].auth_mode == "api_key"
    assert specs[1].credentials[0].key == "personal_access_token"


def test_connector_catalog_dir_prefers_open_connector(monkeypatch, tmp_path) -> None:
    from basis.services.connector.synthesis.paths import connector_catalog_dir

    oc_apps = tmp_path / "open-connector" / "catalog" / "apps"
    oc_apps.mkdir(parents=True)
    (oc_apps / "demo.json").write_text("{}", encoding="utf-8")

    legacy = tmp_path / "legacy" / "apps"
    legacy.mkdir(parents=True)
    (legacy / "other.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("BASIS_SYNTHESIS_OPEN_CONNECTOR_ROOT", str(oc_apps.parent.parent))
    monkeypatch.setenv("BASIS_SYNTHESIS_ANYCONNECT_CATALOG", str(legacy))

    assert connector_catalog_dir() == oc_apps
