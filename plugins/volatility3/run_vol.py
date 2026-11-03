"""Runs a fixed set of Volatility 3 plugins with JSON output (inside the tool image).

Usage: run_vol.py <memory image> <output dir>
Symbols are bundled in the image; the container has no network access.
"""

import subprocess
import sys
from pathlib import Path

mem, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
SETS = {
    "windows": [
        "windows.info",
        "windows.pslist",
        "windows.psscan",
        "windows.cmdline",
        "windows.netscan",
        "windows.malfind",
        "windows.svcscan",
    ],
    "linux": ["linux.pslist", "linux.bash", "linux.sockstat"],
    "mac": ["mac.pslist", "mac.bash", "mac.netstat"],
}


def vol(plugin: str) -> bool:
    print(f"$ vol {plugin}", flush=True)
    with (out / f"{plugin}.json").open("w") as f:
        r = subprocess.run(
            ["vol", "-q", "--offline", "-r", "json", "-f", mem, plugin],  # noqa: S607
            stdout=f,
            stderr=subprocess.PIPE,
            text=True,
        )
    if r.returncode != 0:
        print(r.stderr[-2000:], flush=True)
        (out / f"{plugin}.json").unlink(missing_ok=True)
        return False
    return True


os_name = next(
    (
        o
        for o, probe in (
            ("windows", "windows.info"),
            ("linux", "linux.pslist"),
            ("mac", "mac.pslist"),
        )
        if vol(probe)
    ),
    None,
)
if os_name is None:
    print("could not identify the operating system of this memory image", file=sys.stderr)
    sys.exit(2)
print(f"profile: {os_name}", flush=True)
for p in SETS[os_name]:
    if not (out / f"{p}.json").exists():
        vol(p)
