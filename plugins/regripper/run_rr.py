"""Run RegRipper's automatic plugin set on every registry hive found.

Usage: run_rr.py <evidence> <out>
"""

import subprocess
import sys
from pathlib import Path

HIVES = {
    "system",
    "software",
    "sam",
    "security",
    "ntuser.dat",
    "usrclass.dat",
    "amcache.hve",
    "default",
}
src = Path(
    subprocess.run(
        ["python", "/opt/stage.py", sys.argv[1], sys.argv[2]],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)
out = Path(sys.argv[2]) / "regripper"
out.mkdir(parents=True, exist_ok=True)
hives = (
    [src]
    if src.is_file()
    else [p for p in sorted(src.rglob("*")) if p.is_file() and p.name.lower() in HIVES]
)
print(f"{len(hives)} hives", flush=True)
for i, h in enumerate(hives):
    rel = h.name if src.is_file() else str(h.relative_to(src))
    print(f"[{i + 1}/{len(hives)}] {rel}", flush=True)
    with (out / f"{i:04d}.txt").open("w") as o:
        o.write(f"#HIVE {rel}\n")
        o.flush()
        subprocess.run(
            ["regripper", "-r", str(h), "-a"], stdout=o, stderr=subprocess.STDOUT, check=False
        )
