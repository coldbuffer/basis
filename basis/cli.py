"""Basis CLI: HTTP service and operational commands."""

from __future__ import annotations

import argparse
import os
import socket
import sys
from dataclasses import replace

import uvicorn

from basis.infra.runtime.config import Settings
from basis.infra.observability.logging_setup import uvicorn_log_config


def _allocate_listen_port(host: str, port: int) -> int:
    if port != 0:
        return port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _cmd_serve(settings: Settings) -> None:
    settings.validate_for_startup()
    listen_port = _allocate_listen_port(settings.host, settings.port)
    if listen_port != settings.port:
        settings = replace(settings, port=listen_port)
    os.environ["BASIS_LISTEN_PORT_RESOLVED"] = "1"
    os.environ["BASIS_PORT"] = str(listen_port)
    uvicorn.run(
        "basis.app:create_app",
        host=settings.host,
        port=listen_port,
        factory=True,
        log_config=uvicorn_log_config(settings),
    )


def _cmd_migrate_legacy_graphs(settings: Settings, args: argparse.Namespace) -> None:
    from basis.services.tenancy.admin.store import AdminStore
    from basis.services.graph.projection.snapshot_store import GraphPersistence
    from basis.services.knowledge.blob_store import BlobStore
    from basis.services.knowledge.store import KnowledgeStore
    from basis.infra.migration.legacy_graph import migrate_all_legacy_graphs, print_reports

    admin = AdminStore(settings.db_path)
    try:
        workspace_ids = list(args.workspace_id) if args.workspace_id else admin.list_workspace_ids()
    finally:
        admin.close()

    knowledge = KnowledgeStore(settings.db_path, BlobStore(settings.data_dir))
    persistence = GraphPersistence(settings.data_dir)
    try:
        reports = migrate_all_legacy_graphs(
            knowledge,
            persistence,
            workspace_ids,
            dry_run=args.dry_run,
            rebuild_projection=args.rebuild,
        )
    finally:
        knowledge.close()

    print_reports(reports)
    if any(report.get("unmappable") for report in reports):
        sys.exit(2 if args.dry_run else 1)


def _cmd_postgres_reset_schema(settings: Settings) -> None:
    from sqlalchemy import create_engine

    from basis.infra.db.alembic_upgrade import upgrade_postgres_engine
    from basis.infra.db.postgres_migrations import reset_postgres_public_schema

    url = settings.database_url
    if not url or not url.startswith("postgres"):
        print("BASIS_DATABASE_URL must be a PostgreSQL URL", file=sys.stderr)
        sys.exit(1)
    sqlalchemy_url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(sqlalchemy_url)
    try:
        reset_postgres_public_schema(engine)
        upgrade_postgres_engine(engine)
    finally:
        engine.dispose()
    print("PostgreSQL schema rebuilt (alembic upgrade head).")


def _cmd_migrate_postgres(settings: Settings, args: argparse.Namespace) -> None:
    from basis.infra.migration.sqlite_to_postgres import migrate_sqlite_to_postgres

    report = migrate_sqlite_to_postgres(
        settings.db_path,
        args.database_url,
        batch_size=args.batch_size,
        replace=args.replace,
    )
    print(f"Migrated {sum(report['tables'].values())} rows")
    print(f"Chunk hash: {report['chunk_hash']}")
    print("Vector indexes must be rebuilt after switching to PostgreSQL.")


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="basis", description="Basis knowledge platform")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Start the HTTP API (default)")
    serve.add_argument(
        "--profile",
        metavar="NAME|PATH",
        help="Deployment profile (e.g. desktop) or path to profile YAML",
    )
    serve.set_defaults(command="serve", profile=None)

    migrate = sub.add_parser(
        "migrate-legacy-graphs",
        help="Backfill ledger rows from data/graphs/*.json (keeps snapshot files)",
    )
    migrate.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts only; do not write ledger rows",
    )
    migrate.add_argument(
        "--rebuild",
        action="store_true",
        help="After import, rebuild graph projection from ledger and save snapshot",
    )
    migrate.add_argument(
        "--kb-id",
        action="append",
        default=[],
        help="Limit to one or more workspace IDs (workspace_id; repeatable)",
    )
    migrate.set_defaults(command="migrate-legacy-graphs")

    migrate_pg = sub.add_parser(
        "migrate-postgres",
        help="Copy the canonical SQLite database to PostgreSQL and verify chunks",
    )
    migrate_pg.add_argument("--database-url", required=True)
    migrate_pg.add_argument("--batch-size", type=int, default=1000)
    migrate_pg.add_argument("--replace", action="store_true")
    migrate_pg.set_defaults(command="migrate-postgres")

    reset_pg = sub.add_parser(
        "postgres-reset-schema",
        help="Drop public schema and re-apply PostgreSQL migrations (destroys all PG data)",
    )
    reset_pg.set_defaults(command="postgres-reset-schema")

    if not argv:
        settings = Settings.from_env()
        _cmd_serve(settings)
        return

    if argv[0] not in {
        "serve",
        "migrate-legacy-graphs",
        "migrate-postgres",
        "postgres-reset-schema",
        "-h",
        "--help",
    }:
        argv = ["serve", *argv]

    args = parser.parse_args(argv)
    settings = Settings.from_env(profile_spec=getattr(args, "profile", None))

    if args.command == "migrate-legacy-graphs":
        _cmd_migrate_legacy_graphs(settings, args)
        return
    if args.command == "migrate-postgres":
        _cmd_migrate_postgres(settings, args)
        return
    if args.command == "postgres-reset-schema":
        _cmd_postgres_reset_schema(settings)
        return

    _cmd_serve(settings)


if __name__ == "__main__":
    main()
