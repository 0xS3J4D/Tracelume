"""ALEAPP (Android Logs Events And Protobuf Parser) plugin.

ALEAPP writes one TSV per artifact module to `<report>/_TSV Exports/<name>.tsv`.
Known modules are mapped to typed artifacts. Everything else becomes a generic `event`
that keeps the whole row in `data`.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.parsers.leapp import parse_report
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext


class AleappPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="aleapp",
        version="0.1.0",
        description="Android artifacts (messages, calls, locations, apps, ...) via ALEAPP",
        tool_name="ALEAPP",
        tool_version="v3.6.0",
        tool_license="MIT",
        tool_url="https://github.com/abrignoni/ALEAPP",
        tool_authors="Alexis Brignoni and contributors",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset({EvidenceKind.android_fs})
    image: ClassVar[str] = "tracelume/aleapp:0.1.0"

    @staticmethod
    def input_type(path: Path) -> str:
        name = path.name.lower()
        if name.endswith(".zip"):
            return "zip"
        if name.endswith((".tar", ".tar.gz", ".tgz")):
            return "tar" if name.endswith(".tar") else "gz"
        return "fs"

    def build_command(self, ctx: RunContext) -> list[str]:
        return [
            "python",
            "/opt/aleapp/aleapp.py",
            "-t",
            self.input_type(ctx.evidence_path),
            "-i",
            str(ctx.evidence_path),
            "-o",
            str(ctx.output_dir),
        ]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        return parse_report(ctx.output_dir)
