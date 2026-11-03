"""iLEAPP (iOS Logs, Events, And Plists Parser) plugin.

Input modes:
- ios_fs: a full file system extraction (.zip / .tar / .tar.gz / folder)
- ios_backup: an iTunes/Finder backup. Because evidence is a single file, the backup folder
  is expected as a .zip. It is unpacked into the job workspace (never next to the original) and
  parsed with `-t itunes`. Encrypted backups are not decrypted.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.parsers.leapp import parse_report
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext

UNZIP = "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])"


def input_type(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".tar"):
        return "tar"
    if name.endswith((".tar.gz", ".tgz")):
        return "gz"
    return "fs"


class IleappPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="ileapp",
        version="0.1.0",
        description="iOS artifacts (iMessage, calls, locations, KnowledgeC, apps, ...) via iLEAPP",
        tool_name="iLEAPP",
        tool_version="v2026.4.6",
        tool_license="MIT",
        tool_url="https://github.com/abrignoni/iLEAPP",
        tool_authors="Alexis Brignoni and contributors",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {EvidenceKind.ios_fs, EvidenceKind.ios_backup}
    )
    image: ClassVar[str] = "tracelume/ileapp:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        out = str(ctx.output_dir)
        if ctx.evidence_kind == EvidenceKind.ios_backup and input_type(ctx.evidence_path) == "zip":
            staged = f"{out}/_backup"
            return [
                "sh", "-c",
                'python -c "$0" "$1" "$2" && python /opt/ileapp/ileapp.py -t itunes '
                '-i "$(find "$2" -name Manifest.db -printf %h -quit)" -o "$3"',
                UNZIP, str(ctx.evidence_path), staged, out,
            ]  # fmt: skip
        mode = (
            "itunes"
            if ctx.evidence_kind == EvidenceKind.ios_backup
            else input_type(ctx.evidence_path)
        )
        return ["python", "/opt/ileapp/ileapp.py", "-t", mode,
                "-i", str(ctx.evidence_path), "-o", out]  # fmt: skip

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        return parse_report(ctx.output_dir)
