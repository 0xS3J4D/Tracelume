"""YARA: scan evidence with the examiner's own rules."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable
from typing import Any, ClassVar

from tracelume.models import EvidenceKind
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext

MAX_RULES = 2 * 1024 * 1024


class YaraPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="yara",
        version="0.1.0",
        description="Scan files (or a whole raw image) with your YARA rules",
        tool_name="YARA",
        tool_version="4.5 (Debian)",
        tool_license="BSD-3-Clause",
        tool_url="https://github.com/VirusTotal/yara",
        tool_authors="VirusTotal",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(EvidenceKind)
    image: ClassVar[str] = "tracelume/yara:0.1.0"
    params_schema: ClassVar[dict[str, Any]] = {
        "rules": {
            "type": "text",
            "label": "YARA rules",
            "required": True,
            "placeholder": 'rule demo { strings: $a = "password" condition: $a }',
        },
    }

    def build_command(self, ctx: RunContext) -> list[str]:
        rules = str(ctx.params.get("rules", "")).encode()
        if not rules.strip() or len(rules) > MAX_RULES:
            raise ValueError("YARA rules are required (max 2 MB)")
        return [
            "python",
            "/opt/run_yara.py",
            str(ctx.evidence_path),
            str(ctx.output_dir),
            base64.b64encode(rules).decode(),
        ]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        path = ctx.output_dir / "yara.json"
        if not path.exists():
            return
        for m in json.loads(path.read_text()):
            yield ArtifactIn(
                type="event",
                title=f"YARA {m['rule']} matched {m['file']}",
                source_path=m["file"],
                data={"module": f"YARA: {m['rule']}", "severity": "high", **m},
            )
