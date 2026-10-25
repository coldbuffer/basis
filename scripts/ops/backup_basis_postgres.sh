#!/usr/bin/env bash
# Logical PostgreSQL dump + optional blob archive (X-03).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${BASIS_DATA_DIR:-$ROOT/data}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${1:-$ROOT/backups}"

if [[ -z "${BASIS_DATABASE_URL:-}" && -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${BASIS_DATABASE_URL:-}" ]] || [[ "${BASIS_DATABASE_URL}" != postgres* ]]; then
  echo "Set BASIS_DATABASE_URL to a postgresql:// connection string (not SQLite)." >&2
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump not found; install PostgreSQL client tools." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
DUMP="$OUT_DIR/basis-pg-$STAMP.dump"
pg_dump "$BASIS_DATABASE_URL" -Fc --no-owner --no-acl -f "$DUMP"
echo "Wrote $DUMP"

if [[ -d "$DATA_DIR/blobs" ]]; then
  BLOBS="$OUT_DIR/basis-blobs-$STAMP.tar.gz"
  tar -czf "$BLOBS" -C "$DATA_DIR" blobs
  echo "Wrote $BLOBS"
fi

if [[ -d "$DATA_DIR/graphs" ]]; then
  GRAPHS="$OUT_DIR/basis-graphs-$STAMP.tar.gz"
  tar -czf "$GRAPHS" -C "$DATA_DIR" graphs
  echo "Wrote $GRAPHS (optional; projections rebuild from ledger)"
fi
