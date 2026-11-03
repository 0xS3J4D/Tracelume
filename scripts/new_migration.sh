#!/usr/bin/env bash
# Create a new schema migration from model changes:  ./scripts/new_migration.sh "add foo to bar"
set -euo pipefail
cd "$(dirname "$0")/../backend"
tmp="$(mktemp -d)"
export TRACELUME_DATABASE_URL="sqlite:///${tmp}/m.db"
.venv/bin/python - "$1" <<'PY'
import sys
from alembic import command
from tracelume.db import alembic_config, get_engine, init_db
init_db()  # bring a scratch DB to head, then diff against the models
cfg = alembic_config()
with get_engine().begin() as conn:
    cfg.attributes["connection"] = conn
    command.revision(cfg, message=sys.argv[1], autogenerate=True)
PY
.venv/bin/ruff format -q tracelume/migrations
rm -rf "$tmp"
