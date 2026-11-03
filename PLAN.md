# PLAN — Tracelume (open source DFIR analysis platform)

> Status: **APPROVED** (2026-11-03). Name: **Tracelume** (*trace* + *lume*, light: shedding light on traces).

## 1. Goals and non-goals

**Goal:** one case database, one plugin system and one web UI over existing open source forensic tools. The platform analyses evidence the examiner **already has, lawfully**.

**In scope:** registering and ingesting evidence (disk images, mobile backups and file system dumps, memory images, logs), running parsers, normalizing their output, unified timeline, search, artifact browsing, tagging, notes, reporting, chain of custody.

**Out of scope (will not be implemented or stubbed):** device unlocking, lock-screen or passcode bypass, exploits, and any acquisition that gets around security controls. The UI and docs will not use any commercial vendor's name, logo or design.

## 2. Architecture

```
┌────────────┐  HTTPS/JSON + SSE   ┌───────────────┐      ┌────────────┐
│ React SPA  │ ──────────────────▶ │ FastAPI (api) │ ───▶ │ PostgreSQL │
│ (Vite)     │ ◀────────────────── │               │      │ (SQLite dev)│
└────────────┘   live logs (SSE)   └──────┬────────┘      └────────────┘
                                          │ enqueue              ▲
                                          ▼                      │ artifacts, job status
                                   ┌─────────────┐               │
                                   │ Redis + RQ  │──▶ worker ────┘
                                   └─────────────┘     │ docker run --network none
                                                       ▼   evidence mounted :ro
                                         ┌──────────────────────────────┐
                                         │ tool images: aleapp, ileapp, │
                                         │ plaso, vol3, sleuthkit, ...  │
                                         └──────────────────────────────┘
```

- **api**: FastAPI + SQLModel. REST for CRUD, Server-Sent Events for live job logs.
- **worker**: an RQ worker. For each job it re-verifies the evidence hash, launches the plugin's tool container, streams stdout/stderr into the job log, then calls `parse_output()` and bulk-inserts artifacts.
- **Tool isolation:** each tool runs as an external CLI inside its own Docker image. The tools are never imported as Python modules, so their licenses and dependencies stay separate. The worker talks to the Docker Engine through the socket. This is a known privilege trade-off and is documented in SECURITY.md; a docker-socket-proxy limited to container create/start/logs is used to narrow it.
- **No outbound network during analysis:** tool containers run with `--network none`. The api and worker sit on an `internal: true` compose network, so they have no egress. The offline map uses bundled tiles, and the UI loads no CDN assets.
- **Storage:** an `evidence/` volume (originals, mounted read-only everywhere except the ingest step, which writes once), a `workspace/` volume (per-job scratch and tool output) and a `reports/` volume.

## 3. Folder structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory
│   │   ├── config.py          # pydantic-settings
│   │   ├── db.py              # engine/session, Alembic hook
│   │   ├── models/            # SQLModel tables (case, evidence, job, artifact, tag, note, audit)
│   │   ├── schemas/           # API request/response models
│   │   ├── api/               # routers: cases, evidence, jobs, artifacts, search, timeline, reports
│   │   ├── services/          # hashing, audit, evidence, jobs, search, reporting
│   │   ├── plugins/           # plugin base class, registry, docker runner
│   │   └── worker.py          # RQ entrypoint
│   ├── migrations/            # Alembic
│   ├── tests/                 # pytest (unit + API), synthetic fixtures
│   └── pyproject.toml
├── plugins/
│   ├── _template/             # copy-me plugin: plugin.py, Dockerfile, manifest.yaml, tests/
│   ├── aleapp/
│   ├── ileapp/
│   ├── plaso/
│   ├── volatility3/
│   └── sleuthkit/
├── frontend/
│   ├── src/{pages,components,api,hooks,viewers}/
│   ├── e2e/                   # Playwright smoke tests
│   └── package.json
├── docs/                      # writing-a-plugin.md, architecture.md, test-data.md, chain-of-custody.md
├── docker-compose.yml
├── .github/workflows/ci.yml
├── README.md  LICENSE  CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md  CREDITS.md
└── PLAN.md
```

## 4. Data model

All timestamps are stored as UTC (`timestamptz`). IDs are UUIDs.

| Table | Key fields |
|---|---|
| **Case** | id, name, number, description, examiner, created_at, status |
| **Evidence** | id, case_id, kind (`disk_image`, `android_fs`, `ios_backup`, `ios_fs`, `memory_image`, `logs`, `other`), original_filename, stored_path, size, sha256, md5, acquired_by, acquired_at, notes, ingested_at, last_verified_at, verify_status |
| **Job** | id, case_id, evidence_id, plugin, plugin_version, params JSON, status (`queued`/`running`/`succeeded`/`failed`/`cancelled`), created_at, started_at, finished_at, exit_code, log_path, artifact_count, error |
| **Artifact** | id, case_id, evidence_id, job_id, type, timestamp (UTC, nullable), timestamp_kind (e.g. `created`, `sent`, `visited`), source_plugin, source_path, title, data JSONB, search_vector (Postgres `tsvector`, GIN index) |
| **Tag** / **ArtifactTag** | tag name and colour; many-to-many with Artifact |
| **Note** | id, case_id, artifact_id (nullable), author, body, created_at |
| **AuditLog** | id, ts, actor, action, case_id, object_type, object_id, details JSON, hash_before, hash_after, prev_entry_hash, entry_hash |

- **Artifact `type` vocabulary**, kept as a controlled enum in `docs/artifact-types.md` and extendable: `message`, `call`, `contact`, `location`, `media`, `web_history`, `app_usage`, `account`, `file_entry`, `process`, `network_connection`, `registry`, `log_event`, `event` (generic). Each type has a documented `data` shape, which the type-specific viewers rely on.
- **Tamper-evident audit log:** each entry stores `entry_hash = sha256(prev_entry_hash + canonical_json(entry))`, so the log forms a hash chain. The api role can only insert into the table, never update or delete. A `verify-audit` endpoint and CLI command recompute the chain.
- **Indexes:** artifact on (case_id, type), (case_id, timestamp) and the GIN search index. JSONB indexes are added later as needed.
- **SQLite in dev:** JSON instead of JSONB, and search falls back to `LIKE`. Postgres-specific code sits behind the search service.

## 5. Evidence handling (chain of custody)

1. **Ingest:** the file is uploaded in chunks or registered from a server-side import directory. It is streamed once while SHA-256 and MD5 are computed together, and the UI shows live hash progress over SSE. It is written to `evidence/<case>/<id>/`, then set read-only (`chmod 0444`) and logged in the audit log.
2. **Before every job:** both hashes are recomputed and compared. On a mismatch the job is marked failed, the evidence is flagged and an audit entry is written. The job never runs on mismatching evidence.
3. **During a job:** the evidence is bind-mounted into the tool container as `:ro`. Disk images are read directly by TSK and Plaso, so nothing is ever mounted read-write. Tool output goes only to `workspace/`.
4. **Audited actions:** case create/edit, evidence ingest/verify, job start/finish, tag and note changes, report export, and settings changes.
5. **Actor:** M1 uses a single configured examiner name from settings or a header. Multi-user authentication is a later milestone (see Q4).

## 6. Plugin interface

```python
class Plugin(ABC):
    meta: PluginMeta            # name, version, description, tool_name, tool_version,
                                # tool_license, tool_url, authors
    supported_evidence: set[EvidenceKind]
    image: str                  # docker image tag, built from plugins/<name>/Dockerfile
    default_params: dict = {}

    def build_command(self, ctx: RunContext) -> list[str]: ...   # CLI args inside container
    def run(self, ctx: RunContext) -> RunResult: ...              # default: DockerRunner using build_command
    def parse_output(self, ctx: RunContext, output_dir: Path) -> Iterable[ArtifactIn]: ...
```

- `RunContext` holds the evidence path inside the container (`/evidence`, read-only), the output directory (`/output`), the params, a logger and the case and evidence IDs.
- `ArtifactIn` is a pydantic model that is validated on insert. It enforces a timezone-aware UTC timestamp and a known `type`.
- **Discovery:** each `plugins/<name>/manifest.yaml` plus an entry point. The registry is shown at `GET /api/plugins`.
- Each plugin is tested on its own: `parse_output()` runs against small synthetic tool output (for example, a fake ALEAPP TSV or SQLite report) without running the real tool. A docker integration test is opt-in.
- `docs/writing-a-plugin.md` and `plugins/_template/` are part of M1.

**ALEAPP mapping:** ALEAPP writes TSV and timeline SQLite output per artifact module. The parser reads ALEAPP's `_TSV Exports/*.tsv`, maps known modules (SMS/MMS, call logs, contacts, Chrome history, location sources, app usage) to typed artifacts, and maps all other modules to `event` with the full row stored in `data`.

## 7. Milestones

| # | Content | Status |
|---|---|---|
| **M1 MVP** | Backend, data model, hashed read-only ingest, audit chain, plugin system, **ALEAPP end to end**, minimal UI, compose, CI | ✅ done (verified with real ALEAPP v3.6.0) |
| **M2 Navigation core** | iLEAPP; **unified timeline** (histogram plus brush to zoom, filters by type, source, evidence and time range); Postgres FTS global search; **command palette (Ctrl+K)** and full keyboard map | |
| **M3 Viewers** | Conversation view (threads, participants), media gallery (offline thumbnails, EXIF), **offline map** (MapLibre with a bundled tile pack and MBTiles import), contact and call views | |
| **M4 Deleted data & SQL** | The Sleuth Kit plugin with a file system browser (including **deleted entries** from `fls -d` and recovered content via `icat`); **SQLite deep parser**: WAL frames, freelist pages and unallocated cells carved into `recovered_record` artifacts and marked as "recovered"; **read-only SQL workbench** (opens *copies* of databases extracted from evidence, plus the case DB through a read-only role, with saved queries); hex viewer | |
| **M5 Investigation workspace** | Tags, bookmarks, notes, **investigation plan board** (hypotheses → tasks → linked artifacts), **entity index** (phone numbers, emails, accounts and device IDs merged across tools, with a link graph), HTML/PDF reports | |
| **M6 AI assistant (local-first)** | See §11 | |
| **M7 More engines** | Plaso, Volatility 3, then RegRipper, Hayabusa, Chainsaw, bulk_extractor, ExifTool, YARA, MVT, unfurl, evtx, MFTECmd; known-file hash sets (NSRL) to hide known-good files and flag known-bad ones | |
| **M8 Production** | Local accounts and roles, a portable **case bundle export/import** (with hashes and audit chain), per-item evidence mounts, COPY-based ingest for more than 10 million artifacts, signed release images, offline installer bundle | |

## 8. CI

GitHub Actions jobs:
- `backend`: ruff, mypy `--strict` on `app/`, pytest on SQLite and Postgres
- `frontend`: eslint, `tsc --noEmit`, vitest
- `e2e`: compose up, then Playwright smoke tests
- `plugins`: builds the plugin images. Not part of the M1 gate, because the images are large.

## 9. Testing data policy

Real evidence is never committed. Fixtures are small, synthetic and generated by scripts in `backend/tests/fixtures/`. `docs/test-data.md` points to NIST CFReDS and Josh Hickman's public Android and iOS images.

## 10. Decisions (resolved)

1. **Name:** Tracelume. Python package `tracelume`, Docker images `tracelume/*`.
2. **Additional tools (M6):** RegRipper, Hayabusa, Chainsaw, bulk_extractor, ExifTool, YARA, MVT, unfurl, evtx_dump, MFTECmd (Eric Zimmerman).
3. **Repository:** a local git repo for now. It will be pushed once an owner/repo is chosen.
4. **Authentication:** single-examiner mode in M1 (the examiner's name comes from settings or the `X-Examiner` header). Accounts come in M7.
5. **Container execution:** through a docker-socket-proxy that only allows container and image calls.
6. **PDF engine:** WeasyPrint.
7. **Distribution:** Tracelume is a downloadable application, not a hosted service. It runs on the examiner's own workstation with `docker compose up`. The UI and API are bound to `127.0.0.1` only and nothing is exposed to the network. Release bundles add a `tracelume` launcher script (Linux/macOS/Windows) and offline image tarballs for air-gapped labs.
8. **Database schema:** M1 uses `create_all`. Alembic migrations are added before the first tagged release, which is the first point where a schema has to stay stable.

## 11. AI assistant (M6) — design

**Principle: evidence never leaves the machine unless the examiner explicitly decides so.**

- **Providers:** a pluggable `LLMProvider` interface. The default is **local** inference:
  `ollama` or a llama.cpp server as an optional compose profile (`--profile ai`) on the internal
  network. Any OpenAI-compatible endpoint can be configured. A **remote** endpoint must be
  enabled per case, the UI shows a banner while it is in use, and the setting is audit-logged.
- **What it does:**
  1. **Ask the case.** Natural-language questions are turned into *structured, inspectable*
     queries (artifact filters or read-only SQL). The examiner sees and can edit the query before
     it runs. Answers cite artifact IDs and link to them.
  2. **Semantic search.** Embeddings are stored in pgvector, giving hybrid FTS and vector search
     over messages, notes and documents.
  3. **Summarise.** It summarises a conversation, a time window or a job's findings, always with
     citations.
  4. **Plan and structure.** It suggests investigation checklists and next steps from the evidence
     types present, and drafts tasks on the plan board. Nothing is created without confirmation.
  5. **SQL helper.** It explains unknown app databases and drafts queries for the SQL workbench.
- **Guardrails:** AI output is always labelled as AI-generated, is never written into
  artifacts, and is never included in a report unless an examiner accepts it. Every prompt,
  provider, model and response hash is written to the audit log. Tool calls are read-only.

## 12. UX principles

- Three panes everywhere (nav, workspace, detail), dark-first, WCAG AA contrast.
- **Keyboard first:** Ctrl+K palette, j/k to move through rows, `t` to tag, `n` to add a note,
  `/` to search, `?` for the shortcut sheet.
- **Never lose context:** filters live in the URL, so any view can be shared or bookmarked,
  and back/forward always works.
- **Provenance is always one glance away:** tool, version, source path, evidence hash and job.
- **Times are always shown in UTC** and labelled. An optional second column shows a chosen local zone.

## 13. Donations

`DONATE.md` plus `.github/FUNDING.yml`: **Monero** (private by default) and **Bitcoin**
addresses supplied by the maintainer. The project never generates or stores keys.
