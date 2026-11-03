"""SQLite extraction and deleted-record recovery (Tracelume's own carver).

Finds every SQLite database in the evidence, keeps a hashed read-only copy for the SQL
workbench, and recovers records from WAL frames, freelist pages and freeblocks.
Recovered records are reported as `recovered_record` artifacts; they are *carved* data and
must be validated against the original database before being relied upon.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, ClassVar

from tracelume.models import EvidenceKind
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext


def possible_times(values: list[Any]) -> list[dict[str, Any]]:
    """Integers that decode to a date between 2000 and 2040 as Unix s/ms/µs or Apple/Mac
    absolute time. Shown as hints only; carved rows have no trusted time."""
    out = []
    lo, hi = datetime(2000, 1, 1, tzinfo=UTC), datetime(2040, 1, 1, tzinfo=UTC)
    for i, v in enumerate(values):
        if not isinstance(v, int) or isinstance(v, bool):
            continue
        for unit, conv in (
            ("unix seconds", lambda x: datetime.fromtimestamp(x, UTC)),
            ("unix milliseconds", lambda x: datetime.fromtimestamp(x / 1000, UTC)),
            ("unix microseconds", lambda x: datetime.fromtimestamp(x / 1_000_000, UTC)),
            (
                "Apple absolute seconds",
                lambda x: datetime.fromtimestamp(x + 978307200, UTC),
            ),
            (
                "Apple absolute nanoseconds",
                lambda x: datetime.fromtimestamp(x / 1e9 + 978307200, UTC),
            ),
        ):
            try:
                dt = conv(v)
            except (OverflowError, OSError, ValueError):
                continue
            if lo <= dt <= hi:
                out.append({"column": i, "unit": unit, "utc": dt.isoformat()})
                break
    return out


def _preview(values: list[Any]) -> str:
    texts = [v for v in values if isinstance(v, str) and v.strip()]
    return " · ".join(t[:80] for t in texts[:3]) or json.dumps(values, default=str)[:120]


class SqliteRecoverPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="sqlite_recover",
        version="0.1.0",
        description="All SQLite databases + deleted-record recovery (WAL, freelist, free space)",
        tool_name="Tracelume SQLite carver",
        tool_version="0.1.0",
        tool_license="GPL-3.0-or-later",
        tool_url="https://github.com/0xS3J4D/tracelume",
        tool_authors="Tracelume contributors",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {
            EvidenceKind.android_fs,
            EvidenceKind.ios_fs,
            EvidenceKind.ios_backup,
            EvidenceKind.other,
        }
    )
    image: ClassVar[str] = "tracelume/sqlite-recover:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return [
            "python",
            "-I",
            "/opt/sqlite_carve.py",
            str(ctx.evidence_path),
            str(ctx.output_dir),
        ]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        index_path = ctx.output_dir / "index.json"
        if not index_path.exists():
            return
        for db in json.loads(index_path.read_text()):
            rc = db.get("recovered", {})
            yield ArtifactIn(
                type="database",
                title=f"SQLite: {db['path']}",
                source_path=db["path"],
                data={
                    **{k: v for k, v in db.items() if k != "tables"},
                    "tables": {n: t["rows"] for n, t in db.get("tables", {}).items()},
                    "recovered_total": sum(rc.values()),
                },
            )
        rec_path = ctx.output_dir / "recovered.jsonl"
        if not rec_path.exists():
            return
        with rec_path.open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                table = r.get("table_guess") or "unknown table"
                yield ArtifactIn(
                    type="recovered_record",
                    title=f"[{r['source']}] {r['db'].rsplit('/', 1)[-1]} › {table}: "
                    f"{_preview(r['values'])}",
                    source_path=r["db"],
                    data={**r, "possible_times_utc": possible_times(r["values"])},
                )
