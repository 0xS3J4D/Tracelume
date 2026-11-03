"""Plaso / log2timeline super-timeline.

`psort -o json_line --output_time_zone UTC` writes one JSON event per line with a
`datetime` (ISO 8601), `timestamp_desc`, `data_type`, `parser`, `message` and `filename`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, ClassVar

from tracelume.models import EvidenceKind
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext

TYPE_PREFIXES: list[tuple[str, str]] = [
    ("fs:", "file_entry"),
    ("windows:registry", "registry"),
    ("windows:evtx", "log_event"),
    ("windows:evt", "log_event"),
    ("syslog", "log_event"),
    ("chrome:history", "web_history"),
    ("firefox:places", "web_history"),
    ("safari:history", "web_history"),
    ("msiecf", "web_history"),
    ("windows:prefetch", "app_usage"),
    ("windows:lnk", "file_entry"),
    ("olecf", "file_entry"),
    ("android:", "event"),
    ("ios:", "event"),
]
DROP = {
    "__container_type__",
    "__type__",
    "message",
    "display_name",
    "datetime",
    "timestamp",
    "timestamp_desc",
}


def classify(data_type: str) -> str:
    for prefix, kind in TYPE_PREFIXES:
        if data_type.startswith(prefix):
            return kind
    return "event"


def parse_dt(v: Any) -> datetime | None:
    if not isinstance(v, str) or v.startswith("Not set") or v.startswith("0000"):
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def event_to_artifact(e: dict[str, Any]) -> ArtifactIn:
    data_type = str(e.get("data_type", ""))
    src = e.get("filename") or e.get("display_name")
    msg = str(e.get("message") or data_type)
    return ArtifactIn(
        type=classify(data_type),
        title=msg[:300],
        timestamp=parse_dt(e.get("datetime")),
        timestamp_kind=e.get("timestamp_desc"),
        source_path=str(src) if src else None,
        data={
            "module": data_type,
            "parser": e.get("parser"),
            "message": msg,
            **{k: v for k, v in e.items() if k not in DROP and not k.startswith("_")},
        },
    )


class PlasoPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="plaso",
        version="0.1.0",
        description="Super-timeline of file system, logs, browsers, registry and more (Plaso)",
        tool_name="Plaso",
        tool_version="20261027",
        tool_license="Apache-2.0",
        tool_url="https://github.com/log2timeline/plaso",
        tool_authors="Joachim Metz, Daniel White and the Plaso developers",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {
            EvidenceKind.disk_image,
            EvidenceKind.logs,
            EvidenceKind.android_fs,
            EvidenceKind.ios_fs,
            EvidenceKind.other,
        }
    )
    image: ClassVar[str] = "tracelume/plaso:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return ["sh", "/opt/run_plaso.sh", str(ctx.evidence_path), str(ctx.output_dir)]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        path = ctx.output_dir / "timeline.jsonl"
        if not path.exists():
            return
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield event_to_artifact(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
