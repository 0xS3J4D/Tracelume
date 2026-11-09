<p align="center"><img src="docs/brand/logo.svg" alt="Tracelume" width="380"></p>

<p align="center"><b>The open source digital forensics workbench.</b><br>
Phones, computers, memory and logs in one case: run trusted open source tools, recover deleted data,
build one timeline, and report it with a verifiable chain of custody. It runs on your own machine,
offline.</p>

<p align="center">
<a href="LICENSE"><img alt="GPL-3.0" src="https://img.shields.io/badge/license-GPL--3.0-2dd4bf"></a>
<a href="https://github.com/0xS3J4D/tracelume/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/0xS3J4D/tracelume/actions/workflows/ci.yml/badge.svg"></a>
<img alt="offline" src="https://img.shields.io/badge/analysis-100%25%20offline-0b1220">
<img alt="status" src="https://img.shields.io/badge/version-0.1.0-f59e0b">
</p>

<p align="center"><img src="docs/screenshots/demo.gif" alt="Tracelume demo: create a case, add a phone dump, run all analyses, review recovered messages, timeline and SQL" width="900"></p>

Tracelume puts the open source forensic tools you already trust behind **one case and one
interface**. Register evidence once, run the tools in isolated containers, and work with all the
results in a single UTC timeline: messages, photos, locations, files, logs and records recovered
from deleted data. Everything you do is written to a tamper-evident audit log, and the case
exports to a PDF report with hashes. It runs on your own computer, and nothing leaves it.

## Try it in 5 minutes
You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS) or Docker Engine 26+ (Linux). Start Docker first.

```bash
git clone https://github.com/0xS3J4D/tracelume
cd tracelume
./tracelume start                                              # macOS / Linux
powershell -ExecutionPolicy Bypass -File .\tracelume.ps1 start  # Windows
```

The first start builds the core tools (10–20 minutes); after that it starts in seconds. Your
browser opens **http://127.0.0.1:8080**. Then:

1. **Cases → Create case.**
2. **Evidence → From the import folder →** `synthetic-android.zip` → type *Android* → **Register evidence**.
   It's a [synthetic phone](demo/README.md) with SMS, a chat app with deleted messages, and geotagged photos.
3. **Run all**, and wait until the jobs show *succeeded*.
4. Open **Artifacts → Recovered (deleted) records**, then try the **Timeline**, the **Map**, the **SQL** tab and **Export PDF report**.

## What works today
Items marked *(beta)* work, but have not yet been tested on real devices or with real AI models.

**Evidence and integrity**
- SHA-256 and MD5 at ingest, read-only storage, re-verification before every analysis
- Hash-chained audit log of every action, with a built-in verifier
- Each tool runs in its own container with no network and sees only its own evidence item
- Register files from an import folder (for large images) or upload them
- iPhone backup over USB (libimobiledevice, Linux hosts) *(beta)*

**Analysis**
| Evidence | Tools |
|---|---|
| Android | ALEAPP · SQLite deleted-record recovery · photos and videos (ExifTool) |
| iPhone | iLEAPP · MVT (spyware indicators) · SQLite recovery · photos and videos |
| Disk images (raw, E01) | The Sleuth Kit, including deleted files and content recovery · Plaso *(beta)* |
| Windows triage (KAPE, Velociraptor) | RegRipper · MFTECmd ($MFT, deleted entries) · Chainsaw · EVTX · Hayabusa *(beta)* |
| Memory images | Volatility 3 (Windows, Linux, macOS) |
| Any file | YARA with your own rules |

**Investigation**
- One timeline for every source, in UTC; drag across the chart to zoom
- Artifact browser with conversation view, photo gallery, offline map and raw data
- Recovered deleted data: SQLite free space, freelists and WAL; deleted files (TSK, $MFT)
- Read-only SQL on every database found in a phone dump
- Search across all cases (Ctrl+K), tags and notes, keyboard shortcuts
- Case assistant (AI): local model by default, shows each step and cites the artifacts it used *(beta)*

**Reporting and operations**
- PDF and HTML report: evidence hashes, processing, tagged findings, notes, audit log
- Case export (.zip) with all artifacts as CSV and JSONL, plus `SHA256SUMS`
- One-click backups in Settings; restore from the launcher
- Runs on Windows, macOS (Intel and Apple Silicon) and Linux

**Planned**: user accounts and roles · scaling past 10 million artifacts · people and accounts
graph across apps · known-file hash sets (NSRL) · more chat-app parsers · encrypted iPhone
backups · a one-click installer. See the [roadmap](docs/architecture.md#7-status-and-roadmap).

## Screenshots
| Recovered deleted messages | Timeline | SQL on a phone database |
|---|---|---|
| ![](docs/screenshots/recovered.png) | ![](docs/screenshots/timeline.png) | ![](docs/screenshots/sql.png) |
| **Photos with GPS on an offline map** | **Case overview** | **Audit log** |
| ![](docs/screenshots/map.png) | ![](docs/screenshots/case-overview.png) | ![](docs/screenshots/audit.png) |

## How it works
A FastAPI backend with PostgreSQL and a job queue, a React interface, and one Docker image per
tool. The worker checks the evidence hash, starts the tool's container with the evidence mounted
read-only and networking disabled, then turns the tool's output into common, UTC-timestamped
artifacts. Details: [architecture](docs/architecture.md) · [chain of custody](docs/chain-of-custody.md) · [security model](SECURITY.md).

**Privacy.** The interface is only reachable from your own computer (127.0.0.1). Tools run without
network access. Tracelume only goes online when you download tool images or an AI model, and it
uses a remote AI service only if you configure one and allow it for a specific case.

## Documentation
[User guide](docs/user-guide.md) · [Case assistant](docs/assistant.md) · [Writing a plugin](docs/writing-a-plugin.md) · [Test data](docs/test-data.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## Legal
Use Tracelume only on data you are legally authorised to examine: under a warrant, with consent,
under your organisation's mandate, or on training data. You are responsible for following the
law, including privacy law. Tracelume does not unlock devices, bypass security or exploit
vulnerabilities, and we don't accept contributions that do. A qualified examiner must validate
the results, including anything the AI assistant says. There is no warranty (GPL-3.0, sections
15–16). The wrapped tools keep their own licences, and some, such as MVT's, add conditions of use;
see [CREDITS.md](CREDITS.md).

## Contributing
Star the repo, report bugs or send a pull request. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits and licence
Tracelume stands on the work of many open source authors. See [CREDITS.md](CREDITS.md).
Licensed under **GPL-3.0-or-later**.

---
<p align="center"><sub>Part of <a href="https://github.com/0xS3J4D">0xS3J4D</a>'s security portfolio</sub></p>
