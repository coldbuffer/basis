import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from basis.domain.knowledge.schedulers.version_ingest_tasks import wait_for_background_ingest
from basis.domain.tenancy.admin.store import AdminStore
from basis.infra.runtime.database import reset_sqlite_database_pool
from tests.support.llm_extract_test_support import TEST_CHAT_LLM, graph_builder_stub_build
from tests.support.test_config import apply_test_config
from tests.support.postgres import (
    create_postgres_database,
    drop_postgres_database,
    postgres_admin_reachable,
    try_create_postgres_database,
)


def pytest_configure() -> None:
    apply_test_config()
    os.environ.setdefault("BASIS_INGEST_INLINE", "1")


@pytest.fixture(autouse=True)
def _isolate_sqlite_pool() -> None:
    yield
    wait_for_background_ingest()
    reset_sqlite_database_pool()


@pytest.fixture(autouse=True)
def _test_chat_llm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AdminStore, "get_chat_llm_settings", lambda self: dict(TEST_CHAT_LLM))

    def _for_entry(self: AdminStore, entry_id: str) -> dict[str, str | None]:
        return {
            **TEST_CHAT_LLM,
            "id": entry_id,
            "provider": "",
        }

    monkeypatch.setattr(AdminStore, "get_chat_llm_settings_for_entry", _for_entry)


@pytest.fixture(autouse=True)
def _stub_llm_graph_builder_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid live LLM calls when jobs use ner/relation method ``llm``."""
    try:
        from semantica.kg import GraphBuilder
    except ImportError:
        return

    _orig = GraphBuilder.build

    def _stub_build(
        self,
        sources,
        second_arg=None,
        pipeline_id=None,
        **options,
    ):
        return graph_builder_stub_build(
            lambda s, sa=None, pid=None, **kw: _orig(self, s, sa, pipeline_id=pid, **kw),
            sources,
            second_arg,
            pipeline_id,
            **options,
        )

    monkeypatch.setattr(GraphBuilder, "build", _stub_build)


@pytest.fixture
def github_integration() -> dict[str, str]:
    """Real GitHub PAT + target repo for REST connector integration tests."""
    token = (os.environ.get("BASIS_TEST_GITHUB_TOKEN") or "").strip()
    if not token:
        pytest.skip(
            "BASIS_TEST_GITHUB_TOKEN is not set; export BASIS_TEST_GITHUB_* for live GitHub tests"
        )
    owner = (os.environ.get("BASIS_TEST_GITHUB_OWNER") or "").strip()
    repo = (os.environ.get("BASIS_TEST_GITHUB_REPO") or "").strip()
    if not owner or not repo:
        pytest.skip(
            "BASIS_TEST_GITHUB_OWNER and BASIS_TEST_GITHUB_REPO are required for live GitHub tests"
        )
    return {"token": token, "owner": owner, "repo": repo}


@pytest.fixture
def postgres_admin_url() -> str:
    admin_url = os.environ.get("BASIS_TEST_POSTGRES_URL")
    if not admin_url:
        pytest.skip(
            "BASIS_TEST_POSTGRES_URL is not configured (tests/test.yaml or env)"
        )
    if not postgres_admin_reachable(admin_url):
        pytest.skip(
            "PostgreSQL is not reachable for integration tests "
            f"({admin_url!r}); start compose.postgres.yml or adjust tests/test.yaml"
        )
    return admin_url


@pytest.fixture
def postgres_url(postgres_admin_url: str) -> str:
    test_url = create_postgres_database(postgres_admin_url)
    yield test_url
    reset_sqlite_database_pool()
    drop_postgres_database(postgres_admin_url, test_url)


def _require_postgres_sql_connector_writable(database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    probe = f"_bocp_probe_{uuid.uuid4().hex[:8]}"
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE {probe} (id int)"))
            conn.execute(text(f"DROP TABLE {probe}"))
    except Exception as exc:
        host = make_url(database_url).host or "localhost"
        port = make_url(database_url).port or 5432
        pytest.skip(
            "PostgreSQL is not writable for BOCP SQL connector tests "
            f"({exc}). Start Basis Postgres: "
            "docker compose -f compose.postgres.yml up -d, then "
            f"Start Postgres (docker compose -f compose.postgres.yml up -d) or set "
            "postgres.sql_target_url in tests/test.yaml "
            f"(host {host}, port {port})."
        )
    finally:
        engine.dispose()


@pytest.fixture
def postgres_sql_target_url(postgres_admin_url: str) -> str:
    """Target DB for BOCP SQL connector tests (tables only; may reuse admin DB locally)."""
    external = os.environ.get("BASIS_TEST_POSTGRES_EXTERNAL_URL")
    if external:
        _require_postgres_sql_connector_writable(external)
        yield external
        return
    test_url, created = try_create_postgres_database(postgres_admin_url)
    _require_postgres_sql_connector_writable(test_url)
    yield test_url
    reset_sqlite_database_pool()
    if created:
        drop_postgres_database(postgres_admin_url, test_url)

