"""Parse every $MFT found (triage collection) with MFTECmd to CSV. Usage: run_mft.py <ev> <out>"""

import subprocess
import sys
from pathlib import Path

src = Path(
    subprocess.run(
        ["python3", "/opt/stage.py", sys.argv[1], sys.argv[2]],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)
out = Path(sys.argv[2]) / "mft"
out.mkdir(parents=True, exist_ok=True)
mfts = (
    [src]
    if src.is_file()
    else [p for p in sorted(src.rglob("*")) if p.is_file() and p.name.lower() == "$mft"]
)
if not mfts:
    print("no $MFT found", file=sys.stderr)
    sys.exit(2)
dll = next(Path("/opt/mftecmd").rglob("MFTECmd.dll"))
for i, m in enumerate(mfts):
    print(f"$MFT: {m}", flush=True)
    subprocess.run(
        ["dotnet", str(dll), "-f", str(m), "--csv", str(out), "--csvf", f"{i:03d}_mft.csv"],
        check=True,
    )
