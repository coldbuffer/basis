#!/usr/bin/env bash
# Pre-push gate: same core checks as README Development (not full CI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ "${BASIS_SKIP_PREPUSH:-}" == "1" ]]; then
  echo "pre-push: skipped (BASIS_SKIP_PREPUSH=1)"
  exit 0
fi

echo "pre-push: uv run pytest -q"
uv run pytest -q

echo "pre-push: web typecheck + unit tests"
(
  cd web
  npm run typecheck
  npm test
)

echo "pre-push: OK"
