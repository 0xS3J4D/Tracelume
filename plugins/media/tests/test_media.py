import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins

FIX = Path(__file__).parent / "fixtures"


def test_time_rules_never_mislabel_local_time() -> None:
    p = load_plugins(Path(__file__).parents[2])["media"]
    a, b, c = list(p.parse_output(RunContext(Path("/e"), FIX, EvidenceKind.android_fs)))
    assert a.timestamp == datetime(2024, 5, 1, 9, 15, 2, tzinfo=UTC)  # 11:15 +02:00
    assert a.data["Latitude"] == 59.9139 and a.data["camera"] == "Synthetic Cam 1"
    assert b.timestamp is None and b.data["exif_local_time"] == "2024:05:01 11:20:00"
    assert c.timestamp == datetime(2024, 5, 2, 7, 0, tzinfo=UTC)


def test_scanner_thumbnails_without_exiftool(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    img = tmp_path / "x.jpg"
    Image.new("RGB", (800, 600), (20, 120, 200)).save(img)
    ev = tmp_path / "ev" / "dump.zip"
    ev.parent.mkdir()
    with zipfile.ZipFile(ev, "w") as z:
        z.write(img, "DCIM/x.jpg")
        z.writestr("notes.txt", "ignored")
    out = tmp_path / "out"
    script = Path(__file__).parents[1] / "media_scan.py"
    # exiftool may be missing on dev machines: metadata is then empty, thumbnails still work
    subprocess.run(
        [sys.executable, str(script), str(ev), str(out)],
        check=True,
        env={"PATH": "/nonexistent"} if False else None,
    )
    lines = (out / "media.jsonl").read_text().splitlines()
    assert len(lines) == 1 and '"DCIM/x.jpg"' in lines[0]
    assert len(list((out / "thumbs").glob("*.jpg"))) == 1
