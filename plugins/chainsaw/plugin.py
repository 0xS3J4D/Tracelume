"""Chainsaw: rapid hunting through Windows event logs with Chainsaw detection rules."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.parsers.common import iso_utc
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext


class ChainsawPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="chainsaw",
        version="0.1.0",
        description="Windows event log hunting with Chainsaw rules (logons, RDP, AV, services…)",
        tool_name="Chainsaw",
        tool_version="v2.17.1",
        tool_license="GPL-3.0",
        tool_url="https://github.com/WithSecureLabs/chainsaw",
        tool_authors="WithSecure Labs",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {EvidenceKind.windows_triage, EvidenceKind.logs}
    )
    image: ClassVar[str] = "tracelume/chainsaw:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        out = ctx.output_dir
        return ["sh", "-c",
                'src="$(python /opt/stage.py "$0" "$1")" && /opt/chainsaw/chainsaw hunt '
                '/opt/chainsaw/rules "$src" --jsonl -o "$1/chainsaw.jsonl" --skip-errors -q',
                str(ctx.evidence_path), str(out)]  # fmt: skip

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        path = ctx.output_dir / "chainsaw.jsonl"
        if not path.exists():
            return
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                docs = d.get("documents") or [d.get("document") or {}]
                ev = (docs[0].get("data") or {}).get("Event", {}) if docs else {}
                system = ev.get("System", {})
                yield ArtifactIn(
                    type="log_event",
                    title=f"[{d.get('level', '?')}] {d.get('name')} — {system.get('Computer', '')}",
                    timestamp=iso_utc(d.get("timestamp")),
                    timestamp_kind="event logged",
                    source_path=docs[0].get("path") if docs else None,
                    data={
                        "module": f"Chainsaw: {d.get('group', '')}",
                        "severity": d.get("level"),
                        "rule": d.get("name"),
                        "authors": d.get("authors"),
                        "event_id": (system.get("EventID") or {}).get("#text")
                        if isinstance(system.get("EventID"), dict)
                        else system.get("EventID"),
                        "channel": system.get("Channel"),
                        "event": ev,
                    },
                )
