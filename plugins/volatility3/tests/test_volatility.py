from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins

FIX = Path(__file__).parent / "fixtures"


def test_vol_json_mapping() -> None:
    p = load_plugins(Path(__file__).parents[2])["volatility3"]
    arts = list(p.parse_output(RunContext(Path("/e"), FIX, EvidenceKind.memory_image)))
    by = {a.title.split(" ")[0] + a.type: a for a in arts}
    procs = [a for a in arts if a.type == "process" and a.title.startswith("PID")]
    assert [a.title for a in procs] == [
        "PID 4 System (PPID 0)",
        "PID 512 smss.exe (PPID 4)",
    ]
    assert procs[1].data["_depth"] == 1
    assert procs[0].timestamp == datetime(2024, 5, 1, 8, 0, tzinfo=UTC)
    net = next(a for a in arts if a.type == "network_connection")
    assert "203.0.113.9:443" in net.title and "chrome.exe" in net.title
    assert any(a.title.startswith("Command line PID 2044") for a in arts)
    assert by
