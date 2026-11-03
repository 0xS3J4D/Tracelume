from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


def test_parse() -> None:
    p = load_plugins(Path(__file__).parents[2])["hayabusa"]
    a, b = p.parse_output(
        RunContext(Path("/e"), Path(__file__).parent / "fixtures", EvidenceKind.windows_triage)
    )
    assert a.timestamp == datetime(2024, 5, 1, 9, 15, 2, 123000, tzinfo=UTC)
    assert a.title == "[low] Logon Failure (Wrong Password) — WS-01"
    assert b.data["severity"] == "high"
