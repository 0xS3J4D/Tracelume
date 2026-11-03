"""The Sleuth Kit: file system listing of disk images, including DELETED entries.

`fls -r -p -m` writes a bodyfile (TSK 3.x format):
    MD5|name|inode|mode|UID|GID|size|atime|mtime|ctime|crtime
Times are Unix epoch seconds (UTC). Deleted names end in " (deleted)" or " (deleted-realloc)".
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from tracelume.models import EvidenceKind
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext

TIME_FIELDS = ("atime", "mtime", "ctime", "crtime")


def _ts(v: str) -> datetime | None:
    try:
        n = int(v)
    except ValueError:
        return None
    return datetime.fromtimestamp(n, tz=UTC) if n > 0 else None


def parse_bodyfile(path: Path) -> Iterator[ArtifactIn]:
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            if len(parts) < 11:
                continue
            # names may contain "|": everything between field 0 and the last 9 fields
            md5, name = parts[0], "|".join(parts[1:-9])
            inode, mode, uid, gid, size, *times = parts[-9:]
            status = "allocated"
            for marker, st in (
                (" (deleted-realloc)", "deleted-realloc"),
                (" (deleted)", "deleted"),
            ):
                if name.endswith(marker):
                    name, status = name[: -len(marker)], st
                    break
            stamps = dict(zip(TIME_FIELDS, (_ts(t) for t in times), strict=True))
            primary = stamps["mtime"] or stamps["crtime"] or stamps["ctime"] or stamps["atime"]
            kind = "dir" if mode.startswith(("d", "r/d")) else "file"
            if name.endswith(("/.", "/..")):
                continue
            yield ArtifactIn(
                type="file_entry",
                title=f"{'[deleted] ' if status != 'allocated' else ''}{name}",
                timestamp=primary,
                timestamp_kind="mtime" if stamps["mtime"] else "first available",
                source_path=name,
                data={
                    "path": name,
                    "status": status,
                    "deleted": status != "allocated",
                    "kind": kind,
                    "inode": inode,
                    "mode": mode,
                    "uid": uid,
                    "gid": gid,
                    "size": int(size) if size.isdigit() else size,
                    "md5": None if md5 in ("0", "") else md5,
                    **{k: v.isoformat() if v else None for k, v in stamps.items()},
                    "volume": path.stem,
                },
            )


class SleuthKitPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="sleuthkit",
        version="0.1.0",
        description="File system listing with deleted files (MACB times) via The Sleuth Kit",
        tool_name="The Sleuth Kit",
        tool_version="4.12",
        tool_license="IPL-1.0 / CPL-1.0 / GPL-2.0+ (per component)",
        tool_url="https://www.sleuthkit.org/sleuthkit/",
        tool_authors="Brian Carrier and contributors",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset({EvidenceKind.disk_image})
    image: ClassVar[str] = "tracelume/sleuthkit:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        cmd = ["python", "/opt/tsk_run.py", str(ctx.evidence_path), str(ctx.output_dir)]
        if ctx.params.get("mode") == "extract":
            p = ctx.params
            if (
                not re.fullmatch(r"[0-9]+(-[0-9]+){0,2}", str(p.get("inode", "")))
                or not str(p.get("offset", "0")).isdigit()
            ):
                raise ValueError("invalid inode or offset")
            cmd += [
                "extract",
                str(p.get("offset", "0")),
                str(p["inode"]),
                Path(str(p.get("name", "recovered.bin"))).name,
            ]
        return cmd

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        meta_path = ctx.output_dir / "recovered" / "recovered.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            yield ArtifactIn(
                type="file_entry",
                title=f"Recovered file content: {ctx.params.get('path', meta['name'])}",
                source_path=str(ctx.params.get("path") or meta["name"]),
                data={
                    **meta,
                    "recovered_file": f"recovered/{meta['name']}",
                    "from_artifact": ctx.params.get("artifact_id"),
                    "deleted": bool(ctx.params.get("deleted")),
                },
            )
            return
        for body in sorted(ctx.output_dir.glob("vol_*.body")):
            yield from parse_bodyfile(body)
