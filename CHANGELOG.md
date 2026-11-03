# Changelog

## 0.1.0 — first public release
- Cases, evidence registration with SHA-256/MD5, read-only storage, re-verification before every job
- Hash-chained audit log with verifier; every action recorded
- Plugin system running each tool in an isolated, network-less container that sees only its own evidence item
- Integrations: ALEAPP, iLEAPP, The Sleuth Kit (deleted files + content recovery), Plaso,
  Volatility 3, Hayabusa, Chainsaw, EVTX, RegRipper, MFTECmd, YARA, MVT, ExifTool media, and
  Tracelume's own SQLite deleted-record recovery
- Unified UTC timeline, artifact browser with conversation/gallery/map views, global search (Ctrl+K)
- Read-only SQL workbench over extracted databases
- Tags, notes, PDF/HTML reports, full case export with checksums
- Optional local-first case assistant with tool calls and verified citations
- iPhone backup over USB (libimobiledevice, Linux, beta), registered as evidence automatically
- In-app backups with checksums; restore from the launcher
- Launchers for Linux/macOS/Windows, prebuilt images, backups, automatic database migrations
- Local-only hardening: host allow-list (DNS rebinding), cross-site write blocking, CSP
