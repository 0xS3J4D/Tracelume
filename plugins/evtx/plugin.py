"""All Windows event log records (evtx_dump), for full-fidelity search and timeline."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, ClassVar

from tracelume.models import EvidenceKind
from tracelume.parsers.common import iso_utc
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext


def _text(v: Any) -> Any:
    return v.get("#text") if isinstance(v, dict) else v


class EvtxPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="evtx",
        version="0.1.0",
        description="Every Windows event log record as searchable artifacts (evtx_dump)",
        tool_name="evtx_dump",
        tool_version="0.15.1",
        tool_license="MIT / Apache-2.0",
        tool_url="https://github.com/omerbenamram/evtx",
        tool_authors="Omer Ben-Amram",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {EvidenceKind.windows_triage, EvidenceKind.logs}
    )
    image: ClassVar[str] = "tracelume/evtx:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return [
            "python",
            "/opt/run_evtx.py",
            str(ctx.evidence_path),
            str(ctx.output_dir),
        ]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        for path in sorted((ctx.output_dir / "evtx").glob("*.jsonl")):
            source = None
            with path.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("# "):
                        source = line[2:].strip()
                        continue
                    try:
                        ev = json.loads(line).get("Event", {})
                    except json.JSONDecodeError:
                        continue
                    sysd = ev.get("System", {})
                    created = (sysd.get("TimeCreated") or {}).get("#attributes", {})
                    eid = _text(sysd.get("EventID"))
                    provider = (sysd.get("Provider") or {}).get("#attributes", {}).get("Name")
                    yield ArtifactIn(
                        type="log_event",
                        title=f"{sysd.get('Channel')} {eid} — {provider or ''} on "
                        f"{sysd.get('Computer', '')}",
                        timestamp=iso_utc(created.get("SystemTime")),
                        timestamp_kind="event logged",
                        source_path=source,
                        data={
                            "module": f"EVTX: {sysd.get('Channel')}",
                            "event_id": eid,
                            "provider": provider,
                            "record_id": sysd.get("EventRecordID"),
                            "computer": sysd.get("Computer"),
                            "event_data": ev.get("EventData") or ev.get("UserData"),
                        },
                    )
