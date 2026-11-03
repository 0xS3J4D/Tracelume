from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


def test_parse() -> None:
    p = load_plugins(Path(__file__).parents[2])["chainsaw"]
    (a,) = p.parse_output(
        RunContext(Path("/e"), Path(__file__).parent / "fixtures", EvidenceKind.logs)
    )
    assert a.title == "[medium] Account Brute Force — WS-01"
    assert a.timestamp == datetime(2024, 5, 1, 9, 15, 2, tzinfo=UTC)
    assert a.data["event_id"] == 4625 and a.source_path == "Security.evtx"
