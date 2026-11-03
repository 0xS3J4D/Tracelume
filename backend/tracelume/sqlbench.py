"""Read-only SQL workbench over SQLite databases extracted by the sqlite_recover plugin.

Safety:
- databases are copies in the job workspace (the evidence is never opened for writing),
  opened with mode=ro&immutable=1;
- an authorizer allows only reads (SELECT, READ, FUNCTION, RECURSIVE, and harmless PRAGMAs);
- a progress handler aborts queries after a time budget; result rows are capped.
"""

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tracelume.config import get_settings

MAX_ROWS = 2000
TIME_BUDGET_S = 8.0
ALLOWED_PRAGMAS = {
    "table_info",
    "table_xinfo",
    "index_list",
    "index_info",
    "foreign_key_list",
    "page_size",
    "page_count",
    "freelist_count",
    "user_version",
    "encoding",
}


class SqlError(Exception):
    pass


@dataclass
class DbRef:
    job_id: str
    file: str
    path: str  # path inside the evidence
    sha256: str
    size: int
    tables: dict[str, Any]
    recovered: dict[str, int]

    @property
    def id(self) -> str:
        return f"{self.job_id}:{self.file}"


def _output(job_id: str) -> Path:
    return get_settings().workspace_dir / "jobs" / job_id / "output"


def list_databases(job_ids: list[str]) -> list[DbRef]:
    refs: list[DbRef] = []
    for job_id in job_ids:
        idx = _output(job_id) / "index.json"
        if not idx.exists():
            continue
        for d in json.loads(idx.read_text()):
            if "file" not in d or "error" in d:
                continue
            refs.append(
                DbRef(
                    job_id,
                    d["file"],
                    d["path"],
                    d["sha256"],
                    d["size"],
                    d.get("tables", {}),
                    d.get("recovered", {}),
                )
            )
    return refs


def resolve(ref_id: str, allowed_jobs: list[str]) -> DbRef:
    job_id, _, file = ref_id.partition(":")
    if job_id not in allowed_jobs:
        raise SqlError("database not found in this case")
    for r in list_databases([job_id]):
        if r.file == file:
            return r
    raise SqlError("database not found")


def _authorizer(action: int, arg1: str | None, *_: Any) -> int:
    if action in (
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        getattr(sqlite3, "SQLITE_RECURSIVE", 33),
    ):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_PRAGMA and (arg1 or "").lower() in ALLOWED_PRAGMAS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _cell(v: Any) -> Any:
    if isinstance(v, bytes):
        return {"blob_hex": v[:256].hex(), "blob_len": len(v)}
    return v


def run_query(ref: DbRef, sql: str) -> dict[str, Any]:
    sql = sql.strip().rstrip(";")
    if not sql:
        raise SqlError("empty query")
    if ";" in sql:
        raise SqlError("one statement at a time")
    path = _output(ref.job_id) / "databases" / ref.file
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        con.execute("PRAGMA trusted_schema=OFF")
        con.set_authorizer(_authorizer)
        deadline = time.monotonic() + TIME_BUDGET_S
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        t0 = time.monotonic()
        try:
            cur = con.execute(sql)
            rows = cur.fetchmany(MAX_ROWS + 1)
        except sqlite3.DatabaseError as e:
            msg = "query timed out" if "interrupted" in str(e) else str(e)
            raise SqlError(msg) from e
        cols = [d[0] for d in cur.description or []]
        return {
            "columns": cols,
            "rows": [[_cell(v) for v in r] for r in rows[:MAX_ROWS]],
            "truncated": len(rows) > MAX_ROWS,
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    finally:
        con.close()


def schema(ref: DbRef) -> list[dict[str, Any]]:
    path = _output(ref.job_id) / "databases" / ref.file
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        con.execute("PRAGMA trusted_schema=OFF")
        out = []
        for name, typ, sql in con.execute(
            "SELECT name, type, sql FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
        ):
            q = name.replace('"', '""')
            cols = [
                {"name": c[1], "type": c[2], "pk": bool(c[5])}
                for c in con.execute(f'PRAGMA table_info("{q}")')
            ]
            out.append(
                {
                    "name": name,
                    "type": typ,
                    "sql": sql,
                    "columns": cols,
                    "rows": ref.tables.get(name, {}).get("rows"),
                }
            )
        return out
    finally:
        con.close()
