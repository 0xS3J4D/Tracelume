from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins

FIX = Path(__file__).parent / "fixtures"


def test_json_line_mapping() -> None:
    p = load_plugins(Path(__file__).parents[2])["plaso"]
    arts = list(p.parse_output(RunContext(Path("/e"), FIX, EvidenceKind.disk_image)))
    assert [a.type for a in arts] == [
        "file_entry",
        "log_event",
        "web_history",
        "file_entry",
    ]
    assert arts[0].timestamp == datetime(2024, 5, 1, 9, 15, 2, tzinfo=UTC)
    assert arts[0].timestamp_kind == "Content Modification Time"
    assert arts[1].data["event_identifier"] == 4624
    assert arts[2].data["url"] == "https://example.org/"
    assert arts[3].timestamp is None
    assert "__container_type__" not in arts[0].data
