from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


def test_parse_detected() -> None:
    p = load_plugins(Path(__file__).parents[2])["mvt"]
    (a,) = p.parse_output(
        RunContext(Path("/e"), Path(__file__).parent / "fixtures", EvidenceKind.ios_fs)
    )
    assert a.title == "MVT indicator match in safari_history: bad.example"
    assert a.data["severity"] == "critical" and a.timestamp is not None
