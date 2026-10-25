#!/usr/bin/env bash
# Restore PostgreSQL dump + optional blobs (destructive). Requires BASIS_RESTORE_CONFIRM=yes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${BASIS_DATA_DIR:-$ROOT/data}"

if [[ $# -lt 1 ]]; then
  echo "Usage: BASIS_RESTORE_CONFIRM=yes $0 <basis-pg.dump> [basis-blobs.tar.gz]" >&2
  exit 1
fi

DUMP="$1"
BLOBS_TAR="${2:-}"

if [[ "${BASIS_RESTORE_CONFIRM:-}" != "yes" ]]; then
  echo "Refusing to restore without BASIS_RESTORE_CONFIRM=yes" >&2
  exit 1
fi

if [[ ! -f "$DUMP" ]]; then
  echo "Dump not found: $DUMP" >&2
  exit 1
fi

if [[ -z "${BASIS_DATABASE_URL:-}" && -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${BASIS_DATABASE_URL:-}" ]] || [[ "${BASIS_DATABASE_URL}" != postgres* ]]; then
  echo "Set BASIS_DATABASE_URL to a postgresql:// connection string." >&2
  exit 1
fi

if ! command -v pg_restore >/dev/null 2>&1; then
  echo "pg_restore not found; install PostgreSQL client tools." >&2
  exit 1
fi

echo "Restoring database from $DUMP into $BASIS_DATABASE_URL"
set +e
pg_restore --clean --if-exists --no-owner --no-acl -d "$BASIS_DATABASE_URL" "$DUMP"
restore_code=$?
set -e
# pg_restore exits 1 when --clean drops missing objects on an empty database.
if [[ "$restore_code" -gt 1 ]]; then
  exit "$restore_code"
fi

if [[ -n "$BLOBS_TAR" ]]; then
  if [[ ! -f "$BLOBS_TAR" ]]; then
    echo "Blobs archive not found: $BLOBS_TAR" >&2
    exit 1
  fi
  mkdir -p "$DATA_DIR"
  tar -xzf "$BLOBS_TAR" -C "$DATA_DIR"
  echo "Extracted blobs into $DATA_DIR"
fi

echo "Done. Start the API and POST /api/v1/workspaces/{workspace_id}/graph/rebuild per workspace if graphs were not restored."
