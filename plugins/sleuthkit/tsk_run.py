"""Runs inside the Sleuth Kit image. Finds partitions with mmls, then lists every file
(allocated and deleted) per file system with `fls -r -p -m`, writing one bodyfile per volume.

Usage: tsk_run.py <image> <output_dir>
"""

import subprocess
import sys
from pathlib import Path

image, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)


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
