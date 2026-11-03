# Security policy

## Reporting a vulnerability
Please **do not** open a public issue. Use GitHub's private vulnerability reporting
(Security → Report a vulnerability) on this repository. We aim to acknowledge reports
within 7 days.

## Threat model (summary)
Tracelume runs on an examiner's own workstation and handles **hostile input**: evidence
may be crafted to attack parsers.

- **Parsers run in throwaway containers** with `--network none`, all capabilities dropped,
  `no-new-privileges`, and a non-root user. Evidence is mounted read-only.
- **Docker API access** goes through `docker-socket-proxy`, which allows only container and
  image endpoints. This is still powerful: anyone who controls the worker can start
  containers. Do not expose the worker or the proxy.
- **Network:** the UI/API port is bound to `127.0.0.1`. Backend services sit on an internal
  Docker network with no internet route. Tracelume makes no outbound calls during analysis.
- **Integrity:** SHA-256 and MD5 are taken at ingest, evidence is re-verified before
  every job, and the audit log is a SHA-256 hash chain (`GET /api/audit/verify`).
  The hash chain makes edits detectable, but it cannot prevent them by someone with
  database access. Export the report or the chain head regularly.
- **Known limitation (M1):** there is no authentication (single-examiner mode), and in compose
  mode a tool container can read the whole evidence volume, not just its own item.
  Both are on the roadmap.

## Scope
Tracelume does not and will not include device unlocking, passcode or lock-screen bypass,
exploits, or any acquisition that circumvents security controls. Pull requests that add these
will be closed.
