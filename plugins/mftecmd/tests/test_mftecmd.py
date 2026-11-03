from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


def test_parse_mft_csv() -> None:
    p = load_plugins(Path(__file__).parents[2])["mftecmd"]
    a, b = p.parse_output(
        RunContext(Path("/e"), Path(__file__).parent / "fixtures", EvidenceKind.windows_triage)
    )
    assert a.data["path"] == ".\\Users\\demo\\report.docx" and not a.data["deleted"]
    assert a.timestamp == datetime(2024, 5, 2, 10, 0, tzinfo=UTC)
    assert a.data["Created0x10"] == "2024-05-01T09:15:02.123456+00:00"
    assert b.data["deleted"] and b.title.startswith("[deleted]")
    assert b.data["possible_timestomp"] is True  # SI created long before FN created
    assert "ZoneId=3" in b.data["zone_id"]
