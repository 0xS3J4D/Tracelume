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
) -> int:
    import docker
    from docker.types import Mount

    client = docker.from_env()
    if settings.evidence_volume and settings.workspace_volume:
        # Worker runs inside compose: mount named volumes (sub-paths resolved by the tool).
        mounts = [
            Mount("/evidence_root", settings.evidence_volume, type="volume", read_only=True),
            Mount("/output_root", settings.workspace_volume, type="volume", read_only=False),
        ]
        tool_ctx = RunContext(
            evidence_path=Path("/evidence_root") / evidence_rel,
            output_dir=Path("/output_root") / output_rel,
            evidence_kind=ctx.evidence_kind,
            params=ctx.params,
        )
    else:
        mounts = [
            # Mount the evidence's own directory so the tool sees the original file name.
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
        tool_ctx = RunContext(
            evidence_path=EVIDENCE_MOUNT / Path(evidence_rel).name,
            output_dir=OUTPUT_MOUNT,
            evidence_kind=ctx.evidence_kind,
            params=ctx.params,
        )
    container = client.containers.run(
        plugin.image,
        plugin.build_command(tool_ctx),
        mounts=mounts,
        network_mode="none",
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        detach=True,
    )
    try:
        for raw in container.logs(stream=True, follow=True):
            on_line(raw.decode("utf-8", "replace").rstrip("\n"))
        result = container.wait()
        return int(result.get("StatusCode", 1))
    finally:
        container.remove(force=True)
