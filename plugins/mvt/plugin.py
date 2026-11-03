"""Mobile Verification Toolkit: check iOS backups / file systems for known spyware indicators.

Only `*_detected.json` results (matches against public IOCs) become artifacts, flagged high.
Note the MVT License 1.1 restricts use; see https://license.mvt.re
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.parsers.common import iso_utc
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext


class MvtPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="mvt",
        version="0.1.0",
        description="iOS spyware indicator check (Pegasus, Predator, …) with public IOCs",
        tool_name="MVT",
        tool_version="2026.11.2",
        tool_license="MVT License 1.1",
        tool_url="https://github.com/mvt-project/mvt",
        tool_authors="Amnesty International Security Lab",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {EvidenceKind.ios_backup, EvidenceKind.ios_fs}
    )
    image: ClassVar[str] = "tracelume/mvt:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return [
            "sh",
            "/opt/run_mvt.sh",
            str(ctx.evidence_path),
            str(ctx.output_dir),
            ctx.evidence_kind.value,
        ]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        for path in sorted((ctx.output_dir / "mvt").glob("*_detected.json")):
            module = path.stem.removesuffix("_detected")
            try:
                rows = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            for r in rows if isinstance(rows, list) else []:
                ioc = r.get("matched_indicator") or {}
                what = (
                    (ioc.get("value") if isinstance(ioc, dict) else ioc)
                    or r.get("url")
                    or r.get("domain")
                    or r.get("process_name")
                    or ""
                )
                ts = r.get("isodate") or r.get("timestamp") or r.get("first_isodate")
                yield ArtifactIn(
                    type="event",
                    title=f"MVT indicator match in {module}: {what}"[:300],
                    timestamp=iso_utc(ts),
                    timestamp_kind="as reported by MVT",
                    data={"module": f"MVT: {module}", "severity": "critical", **r},
                )
