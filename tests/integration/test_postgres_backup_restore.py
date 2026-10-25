"""X-03 — PostgreSQL pg_dump / restore script roundtrip (see tests/test.yaml)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from basis.interface.http.app import create_app
from basis.infra.runtime.config import Settings
from tests.support.postgres import create_postgres_database, drop_postgres_database


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_postgres_backup_restore_scripts_preserve_ledger(
    tmp_path: Path,
    postgres_url: str,
    postgres_admin_url: str,
) -> None:
    if not shutil.which("pg_dump") or not shutil.which("pg_restore"):
        pytest.skip("pg_dump/pg_restore not installed")

    from tests.support.repo_root import REPO_ROOT as repo_root
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    backups = tmp_path / "backups"
    backups.mkdir()

    settings = Settings(
        data_dir=data_dir,
        database_url=postgres_url,
        ingest_inline=True,
    )
    client = TestClient(create_app(settings))
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "pgbackup@example.com",
            "password": "password1",
            "display_name": "PG",
        },
    )
    assert registered.status_code == 200
    headers = _auth(registered.json()["token"])
    workspace_id = client.get("/api/v1/workspaces", headers=headers).json()["workspaces"][0]["id"]
    uploaded = client.post(
        f"/api/v1/workspaces/{workspace_id}/documents/upload",
        headers=headers,
        files={
            "file": (
                "ledger.txt",
                b"Postgres backup roundtrip keeps canonical ledger rows.",
                "text/plain",
            )
        },
        data={"extract": "false", "wait": "true"},
    )
    assert uploaded.status_code == 200
    client.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers)
    client.close()

    backup_env = {
        **os.environ,
        "BASIS_DATABASE_URL": postgres_url,
        "BASIS_DATA_DIR": str(data_dir),
    }
    subprocess.run(
        [str(repo_root / "scripts/ops/backup_basis_postgres.sh"), str(backups)],
        env=backup_env,
        check=True,
        cwd=repo_root,
    )
    dumps = sorted(backups.glob("basis-pg-*.dump"))
    assert len(dumps) == 1
    blob_archives = sorted(backups.glob("basis-blobs-*.tar.gz"))

    restore_url = create_postgres_database(postgres_admin_url)
    try:
        restore_env = {
            **os.environ,
            "BASIS_DATABASE_URL": restore_url,
            "BASIS_DATA_DIR": str(data_dir),
            "BASIS_RESTORE_CONFIRM": "yes",
        }
        restore_cmd = [
            str(repo_root / "scripts/ops/restore_basis_postgres.sh"),
            str(dumps[0]),
        ]
        if blob_archives:
            restore_cmd.append(str(blob_archives[0]))
        subprocess.run(restore_cmd, env=restore_env, check=True, cwd=repo_root)

        client2 = TestClient(
            create_app(
                Settings(
                    data_dir=data_dir,
                    database_url=restore_url,
                    ingest_inline=True,
                )
            )
        )
        login = client2.post(
            "/api/v1/auth/login",
            json={"email": "pgbackup@example.com", "password": "password1"},
        )
        assert login.status_code == 200
        headers2 = _auth(login.json()["token"])
        docs = client2.get(
            f"/api/v1/workspaces/{workspace_id}/documents", headers=headers2
        ).json()["documents"]
        # List API omits `filename` when title matches `{external_key}.txt` (ledger upload).
        assert any(
            d.get("doc_id") == "ledger"
            or d.get("filename") == "ledger.txt"
            or "backup roundtrip" in (d.get("preview") or "")
            for d in docs
        )

        rebuild = client2.post(f"/api/v1/workspaces/{workspace_id}/graph/rebuild", headers=headers2)
        assert rebuild.status_code == 200
        snap = client2.get(
            f"/api/v1/workspaces/{workspace_id}/graph/snapshot", headers=headers2
        ).json()
        node_ids = {n["id"] for n in snap["nodes"]}
        assert any("ledger" in nid for nid in node_ids)
        client2.close()
    finally:
        drop_postgres_database(postgres_admin_url, restore_url)
