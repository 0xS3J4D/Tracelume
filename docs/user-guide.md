# User guide

## 1. Start
`./tracelume start` (Windows: `.\tracelume.ps1 start`) opens http://127.0.0.1:8080.
First set your name under **Settings → Examiner**. It is recorded in the audit log and in reports.

## 2. Create a case
**Cases → Create case.** A case holds evidence, results, tags, notes and its own audit trail.
A case can be **closed** (header → *Close case*) to freeze it: no new evidence or analyses are
allowed until it is reopened.

## 3. Register evidence
**Evidence tab.** Either upload a file, or, for large images, copy it into the `import/`
folder next to Tracelume and register it from there through the API
(`POST /api/cases/{id}/evidence/import`). Choose the correct type:

| Type | Typical files |
|---|---|
| Android file system / backup | full file system `.zip`/`.tar` from your extraction tool |
| iOS file system | full file system `.zip`/`.tar` |
| iOS backup | iTunes/Finder backup folder, zipped (unencrypted) |
| Disk image | raw/dd, E01 |
| Memory image | raw, lime, vmem, dmp |
| Windows triage collection | KAPE / Velociraptor output, zipped |
| Logs | single `.evtx` or a zip of logs |

Tracelume computes SHA-256 and MD5 while storing the file, and marks the stored copy read-only.
Use **Re-verify** at any time. Hashes are also checked automatically before every analysis.

### iPhone backup over USB (Linux, beta)
On the Evidence tab, open **Acquire an iPhone backup over USB**, connect and unlock the phone,
click **Find connected iPhones**, and then **Start backup**. Tap *Trust* on the phone the first
time. The finished backup is zipped, hashed and registered as *iOS backup* evidence, with the
device model, iOS version and serial in its notes. If the host runs its own `usbmuxd`, stop it
first (`sudo systemctl stop usbmuxd`). On Windows and macOS, make the backup with Finder/iTunes or
Apple Devices instead, zip the folder, and register it.

## 4. Analyse
**Run all** starts every analysis that fits the evidence type. **Choose…** lets you pick one
analysis. YARA asks for your rules. Each analysis is a job with a live log (**Jobs** tab) and
can be cancelled.

## 5. Investigate
- **Timeline**: all timestamped artifacts in UTC. Drag across the chart to zoom, and toggle types with the chips.
- **Artifacts**: a table, plus **Conversation** (messages), **Gallery** (photos/videos) and **Map** (anything with coordinates).
  Recovered (deleted) records are a separate type. They are carved data, so verify them against the source database.
- **SQL**: every SQLite database found by the *SQLite carver*, with read-only queries.
- **Detail panel**: provenance (tool, source path, IDs), tags (`t`), notes (`n`), raw data,
  and *Recover deleted file content* for Sleuth Kit file entries.
- **Ctrl+K**: jump to any case or view, or search artifact content across all cases.

### About time
All times are stored and shown in **UTC**. Camera EXIF times are often local time with no zone.
Tracelume uses them only when an offset or GPS time is present. Otherwise it shows them with a
warning instead of guessing. Values in recovered records that look like timestamps are shown as
*hints*, with the unit that matched.

## 6. Assistant (optional)
See [assistant.md](assistant.md). Treat its answers as leads: open every citation and verify it.

## 7. Report and export
- **Export PDF report**: case details, evidence hashes and integrity status, processing steps,
  tagged findings with notes, examiner notes, the full audit log and the audit chain status.
- **Export case (.zip)**: the report plus every artifact (CSV/JSONL), the audit log, the evidence
  manifest and `SHA256SUMS`, for archiving or for review in other tools.
Every export is recorded in the audit log together with its SHA-256.

## 8. Back up and update
**Settings → Backups → Create backup now** (or `./tracelume backup`) writes one archive with the
database, evidence and results to the `backups/` folder, with a `.sha256` file next to it.
Restore it into a fresh installation with `./tracelume restore backups/<file>.tar.gz`.
`./tracelume update` updates the program. Database migrations run automatically.

## Keyboard
`Ctrl/⌘+K` palette · `/` search · `j`/`k` move · `t` tag · `n` note · `Ctrl+Enter` save note / run SQL · `?` help
