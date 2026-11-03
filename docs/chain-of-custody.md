# Chain of custody in Tracelume

1. **Ingest:** the file is streamed once. SHA-256 and MD5 are computed while it is written.
   The stored copy is set read-only (0444). An `evidence.ingest` audit entry records the hashes.
2. **Before every job:** both hashes are recomputed. On a mismatch the job is refused, the item is
   flagged `mismatch`, and an `evidence.verify` entry records the before and after hashes.
3. **During a job:** the tool sees the evidence through a read-only mount, in a container with no
   network. It writes only to a separate workspace.
4. **Audit log:** every entry stores `entry_hash = SHA-256(prev_entry_hash ‖ canonical JSON)`.
   `GET /api/audit/verify` recomputes the chain and reports the first broken entry.
5. **Time:** all timestamps are stored and shown in UTC. Each plugin documents the source
   zone of its tool's output.
