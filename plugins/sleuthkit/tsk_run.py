"""Runs inside the Sleuth Kit image.

List mode (default): find partitions with mmls, then list every file (allocated and deleted)
per file system with `fls -r -p -m`, writing one bodyfile per volume.
    tsk_run.py <image> <output_dir>
Extract mode: recover one file's content by inode with icat (works for deleted files whose
data blocks have not been reused).
    tsk_run.py <image> <output_dir> extract <offset> <inode> <name>
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

image, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)

if len(sys.argv) > 3 and sys.argv[3] == "extract":
    offset, inode, name = (
        sys.argv[4],
        sys.argv[5],
        Path(sys.argv[6]).name or "recovered.bin",
    )
    dest = out / "recovered"
    dest.mkdir(exist_ok=True)
    target = dest / name
    print(f"$ icat -r -o {offset} {image} {inode}", flush=True)
    with target.open("wb") as f:
        r = subprocess.run(
            ["icat", "-r", "-o", offset, image, inode],
            stdout=f,  # noqa: S607
            stderr=subprocess.PIPE,
        )
    data = target.read_bytes()
    meta = {
        "name": name,
        "inode": inode,
        "offset": offset,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),  # noqa: S324
        "icat_exit": r.returncode,
        "stderr": r.stderr.decode(errors="replace")[-500:],
    }
    (dest / "recovered.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"recovered {len(data)} bytes, sha256 {meta['sha256']}", flush=True)
    sys.exit(0 if len(data) or r.returncode == 0 else 1)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace")


offsets: list[tuple[int, str]] = []
mm = run(["mmls", "-a", image])
if mm.returncode == 0:
    for line in mm.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[0].rstrip(":").isdigit():
            offsets.append((int(parts[2]), " ".join(parts[5:])))
    print(mm.stdout, flush=True)
if not offsets:
    offsets = [(0, "whole image (no partition table)")]

found = 0
for off, desc in offsets:
    fs = run(["fsstat", "-o", str(off), image])
    if fs.returncode != 0:
        print(f"  offset {off} ({desc}): no recognised file system, skipped", flush=True)
        continue
    fstype = next(
        (
            ln.split(":", 1)[1].strip()
            for ln in fs.stdout.splitlines()
            if ln.startswith("File System Type:")
        ),
        "unknown",
    )
    print(f"  offset {off}: {fstype} ({desc})", flush=True)
    body = run(["fls", "-r", "-p", "-m", f"/vol{off}/", "-o", str(off), image])
    if body.returncode != 0:
        print(body.stderr, flush=True)
        continue
    (out / f"vol_{off}.body").write_text(body.stdout, encoding="utf-8")
    (out / f"vol_{off}.fsstat.txt").write_text(fs.stdout, encoding="utf-8")
    found += 1
    print(f"  {body.stdout.count(chr(10))} entries", flush=True)

if not found:
    print("no file systems found", file=sys.stderr)
    sys.exit(2)
