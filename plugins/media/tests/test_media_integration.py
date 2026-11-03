"""Real media image: ExifTool metadata and thumbnails from a synthetic phone dump."""

import zipfile
from pathlib import Path

from tests.integration_utils import requires_docker, run_tool
from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


@requires_docker
def test_media_image_extracts_exif_and_thumbs(tmp_path: Path) -> None:
    from PIL import Image

    img = tmp_path / "p.jpg"
    exif = Image.Exif()
    exif[0x010F] = "SyntheticCam"  # Make
    Image.new("RGB", (640, 480), (200, 80, 40)).save(img, exif=exif)
    ev = tmp_path / "ev" / "phone.zip"
    ev.parent.mkdir()
    with zipfile.ZipFile(ev, "w") as z:
        z.write(img, "DCIM/Camera/p.jpg")

    plugin = load_plugins(Path(__file__).parents[2])["media"]
    out = tmp_path / "out"
    ctx = RunContext(Path("/evidence/phone.zip"), Path("/output"), EvidenceKind.android_fs)
    run_tool(plugin.image, plugin.build_command(ctx), ev, out)
    (a,) = plugin.parse_output(RunContext(Path("/e"), out, EvidenceKind.android_fs))
    assert a.data["camera"] and "SyntheticCam" in a.data["camera"]
    assert (out / "thumbs" / a.data["thumb"]).exists()
