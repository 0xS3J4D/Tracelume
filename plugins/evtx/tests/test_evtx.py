from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


def test_parse() -> None:
    p = load_plugins(Path(__file__).parents[2])["evtx"]
    a, b = p.parse_output(
        RunContext(Path("/e"), Path(__file__).parent / "fixtures", EvidenceKind.logs)
    )
    assert a.timestamp == datetime(2024, 5, 1, 9, 15, 2, 123456, tzinfo=UTC)
    assert a.data["event_id"] == 4624 and a.source_path == "Logs/Security.evtx"
    assert a.data["event_data"]["LogonType"] == 10
    assert b.data["event_id"] == 7036
