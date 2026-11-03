"""Real Sleuth Kit run on a synthetic FAT image containing a deleted file."""

import subprocess
from pathlib import Path

import pytest

from tests.integration_utils import have, requires_docker, run_tool
from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


@requires_docker
def test_tsk_finds_deleted_file(tmp_path: Path) -> None:
    if not (have("mkfs.fat") and have("mcopy")):
        pytest.skip("needs dosfstools + mtools")
    ev = tmp_path / "ev"
    ev.mkdir()
    img = ev / "disk.img"
    subprocess.run(["mkfs.fat", "-C", str(img), "4096"], check=True, capture_output=True)
    for name, text in (("keep.txt", "kept"), ("gone.txt", "deleted later")):
        src = tmp_path / name
        src.write_text(text)
        subprocess.run(["mcopy", "-i", str(img), str(src), f"::/{name}"], check=True)
    subprocess.run(["mdel", "-i", str(img), "::/gone.txt"], check=True)

    plugin = load_plugins(Path(__file__).parents[2])["sleuthkit"]
    out = tmp_path / "out"
    ctx = RunContext(Path("/evidence/disk.img"), Path("/output"), EvidenceKind.disk_image)
    run_tool(plugin.image, plugin.build_command(ctx), img, out)

    arts = list(plugin.parse_output(RunContext(Path("/e"), out, EvidenceKind.disk_image)))
    names = {a.data["path"].lower(): a for a in arts}
    assert any(p.endswith("keep.txt") and not a.data["deleted"] for p, a in names.items())
    assert any(a.data["deleted"] for a in arts), [a.title for a in arts]
