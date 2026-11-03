"""MFTECmd: NTFS Master File Table — every file record incl. deleted (not in use) entries,
with $STANDARD_INFORMATION (0x10) and $FILE_NAME (0x30) timestamps (UTC)."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.parsers.common import iso_utc
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext

TIMES = (
    "Created0x10",
    "Created0x30",
    "LastModified0x10",
    "LastModified0x30",
    "LastRecordChange0x10",
    "LastRecordChange0x30",
    "LastAccess0x10",
    "LastAccess0x30",
)

csv.field_size_limit(1 << 24)


class MftecmdPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="mftecmd",
        version="0.1.0",
        description="NTFS $MFT: all files incl. deleted records, SI/FN timestamps (timestomping)",
        tool_name="MFTECmd",
        tool_version="2026.10.1",
        tool_license="MIT",
        tool_url="https://github.com/EricZimmerman/MFTECmd",
        tool_authors="Eric Zimmerman",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {EvidenceKind.windows_triage, EvidenceKind.other}
    )
    image: ClassVar[str] = "tracelume/mftecmd:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return ["python3", "/opt/run_mft.py", str(ctx.evidence_path), str(ctx.output_dir)]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        for path in sorted((ctx.output_dir / "mft").glob("*.csv")):
            with path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
                for r in csv.DictReader(f):
                    name = r.get("FileName") or ""
                    if name in (".", "") or name.startswith("$"):
                        continue
                    full = f"{(r.get('ParentPath') or '').rstrip(chr(92))}\\{name}"
                    in_use = (r.get("InUse") or "").lower() == "true"
                    times = {k: iso_utc(r.get(k)) for k in TIMES}
                    si, fn = times["Created0x10"], times["Created0x30"]
                    yield ArtifactIn(
                        type="file_entry",
                        title=f"{'' if in_use else '[deleted] '}{full}",
                        timestamp=times["LastModified0x10"] or si,
                        timestamp_kind="SI modified",
                        source_path=full,
                        data={
                            "module": "NTFS $MFT",
                            "path": full,
                            "deleted": not in_use,
                            "status": "allocated" if in_use else "deleted",
                            "kind": "dir" if r.get("IsDirectory") == "True" else "file",
                            "size": int(r["FileSize"])
                            if (r.get("FileSize") or "").isdigit()
                            else r.get("FileSize"),
                            "entry": r.get("EntryNumber"),
                            "sequence": r.get("SequenceNumber"),
                            "possible_timestomp": bool(si and fn and si < fn),
                            "si_lt_fn_flag": r.get("SI<FN"),
                            "zone_id": r.get("ZoneIdContents"),
                            **{k: v.isoformat() if v else None for k, v in times.items()},
                        },
                    )
