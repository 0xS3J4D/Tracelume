"""Hayabusa: fast Sigma-based threat hunting over Windows event logs (EVTX)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.parsers.common import iso_utc
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext

LEVELS = {
    "crit": "critical",
    "high": "high",
    "med": "medium",
    "low": "low",
    "info": "info",
}


class HayabusaPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="hayabusa",
        version="0.1.0",
        description="Windows event log threat hunting with Sigma rules (detections timeline)",
        tool_name="Hayabusa",
        tool_version="v4.3.1",
        tool_license="AGPL-3.0",
        tool_url="https://github.com/Yamato-Security/hayabusa",
        tool_authors="Yamato Security",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {EvidenceKind.windows_triage, EvidenceKind.logs}
    )
    image: ClassVar[str] = "tracelume/hayabusa:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return ["sh", "/opt/run.sh", str(ctx.evidence_path), str(ctx.output_dir)]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        path = ctx.output_dir / "hayabusa.jsonl"
        if not path.exists():
            return
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                level = LEVELS.get(str(d.get("Level", "")).lower(), d.get("Level"))
                yield ArtifactIn(
                    type="log_event",
                    title=f"[{level}] {d.get('RuleTitle')} — {d.get('Computer', '')}",
                    timestamp=iso_utc(d.get("Timestamp")),
                    timestamp_kind="event logged",
                    source_path=d.get("EvtxFile") or d.get("Channel"),
                    data={
                        "module": f"Hayabusa: {d.get('Channel', '')}",
                        "severity": level,
                        **d,
                    },
                )
