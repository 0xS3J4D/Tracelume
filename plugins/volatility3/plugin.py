"""Volatility 3 memory analysis: processes, command lines, network, injected code, services.

`vol -r json` writes a list of rows; tree plugins nest rows under `__children`.
Volatility reports times in UTC.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, ClassVar

from tracelume.models import EvidenceKind
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext


def flatten(rows: list[dict[str, Any]], depth: int = 0) -> Iterator[dict[str, Any]]:
    for r in rows:
        children = r.pop("__children", []) or []
        yield {**r, "_depth": depth}
        yield from flatten(children, depth + 1)


def ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v or v.startswith("N/A"):
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def to_artifact(plugin: str, r: dict[str, Any]) -> ArtifactIn | None:
    name = plugin.split(".", 1)[1]
    proc = r.get("ImageFileName") or r.get("COMM") or r.get("Process") or r.get("Name")
    pid = r.get("PID") if r.get("PID") is not None else r.get("Pid")
    data = {"module": plugin, **r}
    if name in ("pslist", "psscan"):
        return ArtifactIn(
            type="process",
            title=f"PID {pid} {proc} (PPID {r.get('PPID')})",
            timestamp=ts(r.get("CreateTime")),
            timestamp_kind="process created",
            data=data,
        )
    if name == "cmdline":
        return ArtifactIn(
            type="process",
            title=f"Command line PID {pid} {proc}: {r.get('Args')}",
            data=data,
        )
    if name in ("netscan", "netstat", "sockstat"):
        local = (
            f"{r.get('LocalAddr', r.get('Source Addr', ''))}:"
            f"{r.get('LocalPort', r.get('Source Port', ''))}"
        )
        remote = (
            f"{r.get('ForeignAddr', r.get('Destination Addr', ''))}:"
            f"{r.get('ForeignPort', r.get('Destination Port', ''))}"
        )
        return ArtifactIn(
            type="network_connection",
            title=f"{r.get('Proto', r.get('Protocol', ''))} {local} → {remote} "
            f"{r.get('State', '')} ({r.get('Owner', proc) or '?'})",
            timestamp=ts(r.get("Created")),
            timestamp_kind="connection created",
            data=data,
        )
    if name == "malfind":
        return ArtifactIn(
            type="event",
            title=f"Possible injected code in PID {pid} {proc} ({r.get('Protection')})",
            timestamp=ts(r.get("CommitCharge") and None),
            data=data,
        )
    if name == "svcscan":
        return ArtifactIn(
            type="event",
            title=f"Service {r.get('Name')} ({r.get('State')}) {r.get('Binary') or ''}",
            data=data,
        )
    if name == "bash":
        return ArtifactIn(
            type="event",
            title=f"bash: {r.get('Command')}",
            timestamp=ts(r.get("CommandTime")),
            timestamp_kind="command entered",
            data=data,
        )
    if name == "info":
        return ArtifactIn(
            type="event",
            title=f"System: {r.get('Variable')} = {r.get('Value')}",
            data=data,
        )
    return ArtifactIn(
        type="event", title=f"{plugin}: {json.dumps(r, default=str)[:200]}", data=data
    )


class Volatility3Plugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="volatility3",
        version="0.1.0",
        description="Memory: processes, command lines, network connections, injected code",
        tool_name="Volatility 3",
        tool_version="2.28.2",
        tool_license="Volatility Software License",
        tool_url="https://github.com/volatilityfoundation/volatility3",
        tool_authors="The Volatility Foundation",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset({EvidenceKind.memory_image})
    image: ClassVar[str] = "tracelume/volatility3:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return [
            "python",
            "/opt/run_vol.py",
            str(ctx.evidence_path),
            str(ctx.output_dir),
        ]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        for path in sorted(ctx.output_dir.glob("*.json")):
            try:
                rows = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            for r in flatten(rows if isinstance(rows, list) else []):
                a = to_artifact(path.stem, r)
                if a:
                    yield a
