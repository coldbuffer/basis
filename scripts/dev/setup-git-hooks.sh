#!/usr/bin/env bash
# Point this clone at repo-managed hooks (pre-push runs tests before push).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

chmod +x .githooks/pre-push scripts/dev/pre-push-check.sh scripts/dev/setup-git-hooks.sh

git config core.hooksPath .githooks

echo "Git hooks enabled for this repository (core.hooksPath=.githooks)."
echo "Before each push: scripts/dev/pre-push-check.sh (pytest + web typecheck/test)."
echo "Bypass once: git push --no-verify  |  env BASIS_SKIP_PREPUSH=1 git push"
