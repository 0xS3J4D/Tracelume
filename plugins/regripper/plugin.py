"""RegRipper: Windows registry hive analysis (one artifact per plugin result)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.parsers.common import iso_utc
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext

SEP = re.compile(r"^-{10,}\s*$", re.M)
LASTWRITE = re.compile(r"LastWrite(?: Time)?\s*[:=]?\s*(\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d)Z?")


def sections(text: str) -> Iterator[str]:
    if text.startswith("#HIVE"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    for chunk in SEP.split(text):
        chunk = chunk.strip()
        if chunk:
            yield chunk


class RegRipperPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="regripper",
        version="0.1.0",
        description="Windows registry (SYSTEM, SOFTWARE, SAM, NTUSER, UsrClass, Amcache)",
        tool_name="RegRipper",
        tool_version="3.0",
        tool_license="MIT",
        tool_url="https://github.com/keydet89/RegRipper3.0",
        tool_authors="Harlan Carvey",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {EvidenceKind.windows_triage, EvidenceKind.other}
    )
    image: ClassVar[str] = "tracelume/regripper:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return ["python", "/opt/run_rr.py", str(ctx.evidence_path), str(ctx.output_dir)]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        for path in sorted((ctx.output_dir / "regripper").glob("*.txt")):
            text = path.read_text(encoding="utf-8", errors="replace")
            first = text.splitlines()[0] if text else ""
            hive = first.removeprefix("#HIVE ").strip()
            for sec in sections(text):
                head = sec.splitlines()[0].strip()
                plugin = head.split()[0] if head else "?"
                m = LASTWRITE.search(sec)
                yield ArtifactIn(
                    type="registry",
                    title=f"{hive.rsplit('/', 1)[-1]} › {head}"[:300],
                    timestamp=iso_utc(m.group(1)) if m else None,
                    timestamp_kind="key last written" if m else None,
                    source_path=hive,
                    data={
                        "module": f"RegRipper: {plugin}",
                        "plugin": plugin,
                        "hive": hive,
                        "output": sec[:20000],
                    },
                )
