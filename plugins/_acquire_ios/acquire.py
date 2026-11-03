"""Runs inside the acquisition container (root, USB bus only, no network).

acquire.py list   <out>          -> <out>/devices.json
acquire.py backup <out> <udid>   -> <out>/backup/<udid>/ (idevicebackup2 full backup)
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

mode, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
os.makedirs("/var/run", exist_ok=True)
usbmuxd = subprocess.Popen(
    ["usbmuxd", "-f", "-v", "-U", "root"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT,
)
time.sleep(3)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def info(udid: str) -> dict[str, str]:
    keys = (
        "DeviceName",
        "ProductType",
        "ProductVersion",
        "SerialNumber",
        "UniqueDeviceID",
    )
    r = run(["ideviceinfo", "-u", udid])
    pairs = dict(line.split(": ", 1) for line in r.stdout.splitlines() if ": " in line)
    return {k: pairs.get(k, "") for k in keys} | {"paired": r.returncode == 0}


try:
    if mode == "list":
        udids = [u for u in run(["idevice_id", "-l"]).stdout.split() if u]
        devices = [info(u) | {"udid": u} for u in udids]
        (out / "devices.json").write_text(json.dumps(devices))
        print(f"{len(devices)} device(s)", flush=True)
    elif mode == "backup":
        udid = sys.argv[3]
        if not all(c.isalnum() or c == "-" for c in udid):
            sys.exit("invalid device id")
        pair = run(["idevicepair", "-u", udid, "validate"])
        if pair.returncode != 0:
            print(
                "Not paired yet: unlock the iPhone and tap 'Trust', then enter the passcode.",
                flush=True,
            )
            run(["idevicepair", "-u", udid, "pair"])
            for _ in range(60):
                if run(["idevicepair", "-u", udid, "validate"]).returncode == 0:
                    break
                time.sleep(2)
            else:
                sys.exit("device was not trusted within 2 minutes")
        (out / "device.json").write_text(json.dumps(info(udid)))
        enc = run(["idevicebackup2", "-u", udid, "encryption", "status"]).stdout
        print(enc.strip(), flush=True)
        dest = out / "backup"
        dest.mkdir(exist_ok=True)
        p = subprocess.Popen(
            ["idevicebackup2", "-u", udid, "backup", "--full", str(dest)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert p.stdout is not None
        for line in p.stdout:
            print(line.rstrip(), flush=True)
        if p.wait() != 0:
            sys.exit(f"idevicebackup2 exited with {p.returncode}")
        (out / "encryption.txt").write_text(enc)
    else:
        sys.exit("unknown mode")
finally:
    usbmuxd.terminate()
