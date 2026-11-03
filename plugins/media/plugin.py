"""Media: images and videos with ExifTool metadata, thumbnails and GPS positions.

Time handling: EXIF DateTimeOriginal is usually *local camera time without a zone*. It is
only used as the artifact time when an offset (OffsetTimeOriginal) is present; otherwise
GPSDateTime (UTC by definition) is used; otherwise the time is left empty and the raw local
value is kept in `data.exif_local_time` (clearly labelled, never presented as UTC).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, ClassVar

from tracelume.models import EvidenceKind
from tracelume.plugins.base import ArtifactIn, Plugin, PluginMeta, RunContext


def _exif_dt(v: Any) -> datetime | None:
    if not isinstance(v, str) or v.startswith("0000"):
        return None
    s = v.strip().replace("Z", "+00:00")
    for fmt in ("%Y:%m:%d %H:%M:%S%z", "%Y:%m:%d %H:%M:%S.%f%z", "%Y:%m:%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def pick_time(ex: dict[str, Any]) -> tuple[datetime | None, str | None]:
    local, offset = ex.get("EXIF:DateTimeOriginal"), ex.get("EXIF:OffsetTimeOriginal")
    if local and offset:
        dt = _exif_dt(f"{local}{offset}")
        if dt and dt.tzinfo:
            return dt.astimezone(UTC), "taken (EXIF + offset)"
    gps = _exif_dt(ex.get("Composite:GPSDateTime"))
    if gps:
        return (gps if gps.tzinfo else gps.replace(tzinfo=UTC)).astimezone(UTC), "GPS time"
    qt = _exif_dt(ex.get("QuickTime:CreateDate"))  # QuickTime stores UTC by specification
    if qt:
        return qt.replace(tzinfo=UTC), "created (QuickTime, UTC)"
    return None, None


class MediaPlugin(Plugin):
    meta: ClassVar[PluginMeta] = PluginMeta(
        name="media",
        version="0.1.0",
        description="Photos & videos: EXIF metadata, GPS, thumbnails (ExifTool)",
        tool_name="ExifTool",
        tool_version="13.x (Debian)",
        tool_license="Artistic-1.0 / GPL-1.0+",
        tool_url="https://exiftool.org/",
        tool_authors="Phil Harvey",
    )
    supported_evidence: ClassVar[frozenset[EvidenceKind]] = frozenset(
        {
            EvidenceKind.android_fs,
            EvidenceKind.ios_fs,
            EvidenceKind.ios_backup,
            EvidenceKind.other,
        }
    )
    image: ClassVar[str] = "tracelume/media:0.1.0"

    def build_command(self, ctx: RunContext) -> list[str]:
        return [
            "python",
            "-I",
            "/opt/media_scan.py",
            str(ctx.evidence_path),
            str(ctx.output_dir),
        ]

    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        path = ctx.output_dir / "media.jsonl"
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            for line in f:
                m = json.loads(line)
                ex = m.get("exif", {})
                ts, kind = pick_time(ex)
                data: dict[str, Any] = {
                    "path": m["path"],
                    "kind": m["kind"],
                    "size": m["size"],
                    "sha256": m["sha256"],
                    "thumb": m.get("thumb"),
                    "camera": " ".join(str(ex[k]) for k in ("EXIF:Make", "EXIF:Model") if ex.get(k))
                    or None,
                    "exif_local_time": ex.get("EXIF:DateTimeOriginal"),
                    "exif": ex,
                }
                lat, lon = (
                    ex.get("Composite:GPSLatitude"),
                    ex.get("Composite:GPSLongitude"),
                )
                if isinstance(lat, int | float) and isinstance(lon, int | float):
                    data["Latitude"], data["Longitude"] = lat, lon
                yield ArtifactIn(
                    type="media",
                    title=m["path"].rsplit("/", 1)[-1],
                    timestamp=ts,
                    timestamp_kind=kind,
                    source_path=m["path"],
                    data=data,
                )
