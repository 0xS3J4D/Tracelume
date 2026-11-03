"""Real Plaso run on a small synthetic FAT image."""

import subprocess
from pathlib import Path

import pytest

from tests.integration_utils import have, requires_docker, run_tool
from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


@requires_docker
def test_plaso_builds_timeline(tmp_path: Path) -> None:
    if not (have("mkfs.fat") and have("mcopy")):
        pytest.skip("needs dosfstools + mtools")
    ev = tmp_path / "ev"
    ev.mkdir()
    img = ev / "disk.img"
    subprocess.run(["mkfs.fat", "-C", str(img), "4096"], check=True, capture_output=True)
    note = tmp_path / "note.txt"
    note.write_text("synthetic")
    subprocess.run(["mcopy", "-i", str(img), str(note), "::/note.txt"], check=True)

    plugin = load_plugins(Path(__file__).parents[2])["plaso"]
    out = tmp_path / "out"
    ctx = RunContext(Path("/evidence/disk.img"), Path("/output"), EvidenceKind.disk_image)
    run_tool(plugin.image, plugin.build_command(ctx), img, out)
    arts = list(plugin.parse_output(RunContext(Path("/e"), out, EvidenceKind.disk_image)))
    assert any("note.txt" in (a.source_path or a.title).lower() for a in arts)
    assert all(a.timestamp is None or a.timestamp.tzinfo is not None for a in arts)
