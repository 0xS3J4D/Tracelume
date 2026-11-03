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
- **Isolation per job:** in compose mode each tool container mounts only its own evidence item
  (read-only) and its own output folder, through Docker volume sub-paths (Docker Engine 26+).
- **Browser attacks on a local app:** a host allow-list blocks DNS rebinding, writes from
  foreign origins are rejected (CSRF), and the UI is served with a strict Content-Security-Policy.
- **AI assistant:** local by default. Remote endpoints are refused unless allowed per case,
  API keys are never logged, and assistant tools are read-only and limited to the case.
- **Known limitation:** there is no user authentication (single-examiner workstation model).
  Do not expose port 8080 to a network. For multi-user labs, put Tracelume behind an
  authenticating reverse proxy.

## Scope
Tracelume does not and will not include device unlocking, passcode or lock-screen bypass,
exploits, or any acquisition that circumvents security controls. Pull requests that add these
will be closed.
