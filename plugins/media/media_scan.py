"""Media scanner (runs inside its own container): ExifTool metadata + thumbnails.

Walks a folder, .zip, .tar(.gz) or single file; for every image/video it records path, size,
SHA-256 and ExifTool metadata, and writes a JPEG thumbnail for images.
Writes OUTPUT/media.jsonl and OUTPUT/thumbs/<sha256>.jpg.

Usage: media_scan.py <evidence> <output>
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff"}
VIDEO = {".mp4", ".mov", ".m4v", ".3gp", ".avi", ".mkv", ".webm"}
MAX_FILE = 2 * 1024**3
KEEP = (
    "EXIF:DateTimeOriginal",
    "EXIF:CreateDate",
    "EXIF:OffsetTimeOriginal",
    "EXIF:Make",
    "EXIF:Model",
    "EXIF:Software",
    "EXIF:LensModel",
    "Composite:GPSLatitude",
    "Composite:GPSLongitude",
    "Composite:GPSAltitude",
    "Composite:GPSDateTime",
    "QuickTime:CreateDate",
    "QuickTime:Make",
    "QuickTime:Model",
    "Composite:ImageSize",
    "File:MIMEType",
    "QuickTime:Duration",
    "XMP:CreatorTool",
    "EXIF:UserComment",
    "EXIF:ImageDescription",
)


def members(evidence: Path) -> Iterator[tuple[str, bytes]]:
    name = evidence.name.lower()
    want = IMAGE | VIDEO
    if evidence.is_dir():
        for p in sorted(evidence.rglob("*")):
            if p.is_file() and p.suffix.lower() in want and p.stat().st_size <= MAX_FILE:
                yield str(p.relative_to(evidence)), p.read_bytes()
    elif name.endswith(".zip"):
        with zipfile.ZipFile(evidence) as z:
            for m in z.infolist():
                if (
                    not m.is_dir()
                    and Path(m.filename).suffix.lower() in want
                    and m.file_size <= MAX_FILE
                ):
                    yield m.filename, z.read(m)
    elif name.endswith((".tar", ".tar.gz", ".tgz")):
        with tarfile.open(evidence) as t:
            for m in t:
                if m.isfile() and Path(m.name).suffix.lower() in want and m.size <= MAX_FILE:
                    f = t.extractfile(m)
                    if f:
                        yield m.name, f.read()
    elif evidence.suffix.lower() in want:
        yield evidence.name, evidence.read_bytes()


def exif(paths: list[Path]) -> dict[str, dict[str, object]]:
    if not paths:
        return {}
    try:
        r = subprocess.run(
            ["exiftool", "-json", "-n", "-G", "-q", "-q", *map(str, paths)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("warning: exiftool not found; metadata skipped", flush=True)
        return {}
    try:
        return {d["SourceFile"]: d for d in json.loads(r.stdout or "[]")}
    except json.JSONDecodeError:
        return {}


def thumb(data: bytes, dest: Path) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((320, 320))
            im.convert("RGB").save(dest, "JPEG", quality=78)
        return True
    except Exception:  # noqa: BLE001 — corrupt or unsupported image
        return False


def main() -> None:
    evidence, out = Path(sys.argv[1]), Path(sys.argv[2])
    thumbs = out / "thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        (out / "media.jsonl").open("w", encoding="utf-8") as res,
        tempfile.TemporaryDirectory(dir=out) as tmpd,
    ):
        batch: list[tuple[str, bytes, Path, str]] = []

        def flush() -> None:
            meta = exif([p for _, _, p, _ in batch])
            for rel, data, tmp, digest in batch:
                m = meta.get(str(tmp), {})
                is_img = Path(rel).suffix.lower() in IMAGE
                has_thumb = (
                    is_img
                    and (thumbs / f"{digest}.jpg").exists()
                    or (is_img and thumb(data, thumbs / f"{digest}.jpg"))
                )
                res.write(
                    json.dumps(
                        {
                            "path": rel,
                            "size": len(data),
                            "sha256": digest,
                            "kind": "image" if is_img else "video",
                            "thumb": f"{digest}.jpg" if has_thumb else None,
                            "exif": {k: m[k] for k in KEEP if k in m},
                        },
                        default=str,
                    )
                    + "\n"
                )
                tmp.unlink(missing_ok=True)
            batch.clear()

        for rel, data in members(evidence):
            digest = hashlib.sha256(data).hexdigest()
            tmp = Path(tmpd) / f"{digest}{Path(rel).suffix.lower()}"
            tmp.write_bytes(data)
            batch.append((rel, data, tmp, digest))
            count += 1
            if len(batch) >= 200:
                flush()
                print(f"  {count} media files", flush=True)
        flush()
    print(f"done: {count} media files", flush=True)


if __name__ == "__main__":
    main()
