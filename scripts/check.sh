#!/usr/bin/env bash
# Run every check CI runs. Use before each commit:  ./scripts/check.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root/backend"
.venv/bin/ruff check . ../plugins
.venv/bin/ruff format --check . ../plugins
.venv/bin/mypy tracelume
.venv/bin/pytest -q
cd "$root/frontend"
npm run -s lint
npm run -s typecheck
[ "${SKIP_E2E:-}" = 1 ] || npm run -s e2e
echo "✔ all checks passed"
