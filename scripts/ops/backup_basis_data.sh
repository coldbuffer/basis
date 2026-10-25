#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${BASIS_DATA_DIR:-$ROOT/data}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${1:-$ROOT/backups}"
ARCHIVE="$OUT_DIR/basis-data-$STAMP.tar.gz"

mkdir -p "$OUT_DIR"

if [[ ! -d "$DATA_DIR" ]]; then
  echo "Data directory not found: $DATA_DIR" >&2
  exit 1
fi

if [[ -f "$DATA_DIR/basis.db" ]] && command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DATA_DIR/basis.db" "PRAGMA wal_checkpoint(TRUNCATE);"
fi

FILES=()
[[ -f "$DATA_DIR/basis.db" ]] && FILES+=("basis.db")
[[ -f "$DATA_DIR/basis.db-wal" ]] && FILES+=("basis.db-wal")
[[ -f "$DATA_DIR/basis.db-shm" ]] && FILES+=("basis.db-shm")
[[ -d "$DATA_DIR/blobs" ]] && FILES+=("blobs")
[[ -d "$DATA_DIR/graphs" ]] && FILES+=("graphs")

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "Nothing to backup under $DATA_DIR" >&2
  exit 1
fi

tar -czf "$ARCHIVE" -C "$DATA_DIR" "${FILES[@]}"
echo "Wrote $ARCHIVE"
