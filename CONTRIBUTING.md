# Contributing to Tracelume

Thank you! Bug reports, plugins, parsers, docs and UI work are all welcome.

## Ground rules
- **Never commit real evidence** or output from real casework. Use small synthetic fixtures
  (see `scripts/make_synthetic_android.py`) and point to public datasets in `docs/test-data.md`.
- Out of scope: unlocking, bypasses, exploits, or acquisition that circumvents security.
- Don't use any commercial vendor's name, logo or UI design.
- New tools are wrapped as **external processes in their own container**. Don't import them.
  This keeps licences and dependencies isolated. Add the tool to `CREDITS.md`.

## Dev setup
```bash
cd backend && uv venv -p 3.12 && uv pip install -e '.[dev]'
.venv/bin/uvicorn tracelume.main:app --reload        # API on :8000 (SQLite, inline jobs)
cd ../frontend && npm ci && npm run dev               # UI on :5173
```

## Before every commit
```bash
./scripts/check.sh          # everything CI runs (SKIP_E2E=1 to skip the browser test)
```

Keep commits small and well described. One logical change per PR.

## Changing the database schema
Edit `backend/tracelume/models.py`, then run `./scripts/new_migration.sh "describe the change"`
and review the generated file in `backend/tracelume/migrations/versions/`. A test fails
if the models and the migrations drift apart. Migrations run automatically at startup.

## Writing a plugin
See [docs/writing-a-plugin.md](docs/writing-a-plugin.md) and copy `plugins/_template/`.
