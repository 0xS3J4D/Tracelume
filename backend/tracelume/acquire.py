"""iPhone logical backup over USB (libimobiledevice), Linux hosts only.

The acquisition container gets the host USB bus and a persistent pairing store, nothing else
(no network, no evidence volume). The finished backup is zipped and registered as evidence
through the normal ingest path, so it is hashed, stored read-only and audit-logged.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tracelume.config import Settings

PLUGIN = "ios_acquire"
IMAGE = "tracelume/acquire-ios:0.1.0"


def run_container(
    settings: Settings,
    argv: list[str],
    out_rel: str,
    on_line: Callable[[str], None],
    cancelled: Callable[[], bool],
) -> int:
    import threading

    import docker
    from docker.types import Mount

    client = docker.from_env(version="auto")
    image = f"{settings.image_registry.rstrip('/')}/{IMAGE}" if settings.image_registry else IMAGE
    if settings.workspace_volume:
        out = Mount("/output", settings.workspace_volume, type="volume")
        out["VolumeOptions"] = {"Subpath": out_rel}
    else:
        out = Mount("/output", str((settings.workspace_dir / out_rel).resolve()), type="bind")
    mounts = [out, Mount("/var/lib/lockdown", "tracelume_lockdown", type="volume")]
    container = client.containers.run(
        image,
        ["python3", "/opt/acquire.py", *argv[:1], "/output", *argv[1:]],
        mounts=mounts,
        network_mode="none",
        detach=True,
        volumes={"/dev/bus/usb": {"bind": "/dev/bus/usb", "mode": "rw"}},
        device_cgroup_rules=["c 189:* rmw"],
        labels={"tracelume.job": out_rel},
    )
    stop = threading.Event()

    def watch() -> None:
        while not stop.wait(2.0):
            if cancelled():
                on_line("[tracelume] cancellation requested — stopping backup")
                container.kill()
                return

    threading.Thread(target=watch, daemon=True).start()
    try:
        for raw in container.logs(stream=True, follow=True):
            on_line(raw.decode("utf-8", "replace").rstrip("\n"))
        return int(container.wait().get("StatusCode", 1))
    finally:
        stop.set()
        container.remove(force=True)


def zip_backup(out_dir: Path, udid: str) -> Path:
    src = out_dir / "backup" / udid
    if not (src / "Manifest.db").exists() and not (src / "Manifest.plist").exists():
        raise RuntimeError("backup folder is incomplete (no Manifest)")
    target = out_dir / f"iphone-backup-{udid}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, f"{udid}/{p.relative_to(src)}")
    return target


def device_info(out_dir: Path) -> dict[str, Any]:
    p = out_dir / "device.json"
    return json.loads(p.read_text()) if p.exists() else {}


ACQ_RUNNER = run_container
