"""Runs a plugin's tool image with no network and read-only evidence."""

from collections.abc import Callable
from pathlib import Path

from tracelume.config import Settings
from tracelume.plugins.base import Plugin, RunContext

EVIDENCE_MOUNT = Path("/evidence")
OUTPUT_MOUNT = Path("/output")


def run_in_docker(
    plugin: Plugin,
    settings: Settings,
    evidence_rel: str,
    output_rel: str,
    ctx: RunContext,
    on_line: Callable[[str], None],
    cancelled: Callable[[], bool] = lambda: False,
) -> int:
    import docker
    from docker.types import Mount

    client = docker.from_env(version="auto")
    ev_name = Path(evidence_rel).name
    tool_ctx = RunContext(
        evidence_path=EVIDENCE_MOUNT / ev_name,
        output_dir=OUTPUT_MOUNT,
        evidence_kind=ctx.evidence_kind,
        params=ctx.params,
    )
    if settings.evidence_volume and settings.workspace_volume:
        # Worker runs inside compose: mount ONLY this evidence item's directory and this job's
        # output directory, using volume sub-paths (Docker Engine >= 26).
        ev_mount = Mount(
            str(EVIDENCE_MOUNT), settings.evidence_volume, type="volume", read_only=True
        )
        ev_mount["VolumeOptions"] = {"Subpath": str(Path(evidence_rel).parent)}
        out_mount = Mount(str(OUTPUT_MOUNT), settings.workspace_volume, type="volume")
        out_mount["VolumeOptions"] = {"Subpath": output_rel}
        mounts = [ev_mount, out_mount]
        on_line("[tracelume] tool sees only this evidence item (read-only) and its own output")
    else:
        # Mount the evidence's own directory so the tool sees the original file name.
        mounts = [
            Mount(
                str(EVIDENCE_MOUNT),
                str((settings.evidence_dir / evidence_rel).parent.resolve()),
                type="bind",
                read_only=True,
            ),
            Mount(
                str(OUTPUT_MOUNT),
                str((settings.workspace_dir / output_rel).resolve()),
                type="bind",
                read_only=False,
            ),
        ]
    container = client.containers.run(
        plugin.image,
        plugin.build_command(tool_ctx),
        mounts=mounts,
        network_mode="none",
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        pids_limit=4096,
        labels={"tracelume.job": output_rel},
        detach=True,
    )
    import threading

    stop = threading.Event()

    def watch() -> None:
        while not stop.wait(2.0):
            if cancelled():
                on_line("[tracelume] cancellation requested — stopping tool container")
                container.kill()
                return

    threading.Thread(target=watch, daemon=True).start()
    try:
        for raw in container.logs(stream=True, follow=True):
            on_line(raw.decode("utf-8", "replace").rstrip("\n"))
        result = container.wait()
        return int(result.get("StatusCode", 1))
    finally:
        stop.set()
        container.remove(force=True)
