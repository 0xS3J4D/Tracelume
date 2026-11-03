from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


def test_parse_sections() -> None:
    p = load_plugins(Path(__file__).parents[2])["regripper"]
    a, b = p.parse_output(
        RunContext(Path("/e"), Path(__file__).parent / "fixtures", EvidenceKind.windows_triage)
    )
    assert a.title == "SYSTEM › compname v.20090727" and "WS-01" in a.data["output"]
    assert a.timestamp is None
    assert b.data["plugin"] == "timezone"
    assert b.timestamp == datetime(2024, 5, 1, 9, 15, 2, tzinfo=UTC)
