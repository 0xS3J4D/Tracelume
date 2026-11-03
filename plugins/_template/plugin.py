"""TEMPLATE — copy this folder to plugins/<your_tool>/ and fill in the blanks.

Folders starting with "_" are ignored by the plugin registry.
See docs/writing-a-plugin.md.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext


class MyToolPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="mytool",  # unique, lowercase; used in the API and the DB
        version="0.1.0",  # version of THIS plugin
        description="One line describing what this extracts",
        tool_name="MyTool",
        tool_version="1.2.3",  # pinned in the Dockerfile
        tool_license="Apache-2.0",
        tool_url="https://example.org/mytool",
        tool_authors="Original authors",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset({EvidenceKind.logs})
    image: ClassVar[str] = "tracelume/mytool:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        # Runs inside the tool image with --network none.
        # ctx.evidence_path is read-only; write ONLY to ctx.output_dir.
        return [
            "mytool",
            "--json",
            "-o",
            f"{ctx.output_dir}/out.jsonl",
            str(ctx.evidence_path),
        ]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        out = ctx.output_dir / "out.jsonl"
        if not out.exists():
            return
        with out.open(encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                yield ArtifactIn(
                    type="log_event",  # one of tracelume.plugins.base.ARTIFACT_TYPES
                    title=rec.get("message", "")[:200],
                    # Always timezone-aware UTC. Convert local times explicitly.
                    timestamp=datetime.fromtimestamp(rec["epoch"], tz=UTC)
                    if rec.get("epoch")
                    else None,
                    timestamp_kind="logged",
                    source_path=rec.get("file"),
                    data=rec,
                )
