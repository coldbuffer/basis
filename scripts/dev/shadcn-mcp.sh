#!/usr/bin/env bash
# Run shadcn MCP from web/ (where components.json lives).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/web"
if [ -f .env.local ]; then
  set -a
  # shellcheck source=/dev/null
  . ./.env.local
  set +a
elif [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  . ./.env
  set +a
fi
exec npx -y shadcn@latest mcp
