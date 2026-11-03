"""Dump every .evtx record to JSON lines. Usage: run_evtx.py <evidence> <out>"""

import subprocess
import sys
from pathlib import Path

src = Path(
    subprocess.run(
        ["python", "/opt/stage.py", sys.argv[1], sys.argv[2]],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)
out = Path(sys.argv[2]) / "evtx"
out.mkdir(parents=True, exist_ok=True)
files = [src] if src.is_file() else sorted(p for p in src.rglob("*") if p.suffix.lower() == ".evtx")
for i, f in enumerate(files):
    rel = f.name if src.is_file() else str(f.relative_to(src))
    print(f"[{i + 1}/{len(files)}] {rel}", flush=True)
    with (out / f"{i:05d}.jsonl").open("w") as o:
        o.write(f"# {rel}\n")
        o.flush()
        subprocess.run(["evtx_dump", "-o", "jsonl", "-t", "2", str(f)], stdout=o, check=False)
