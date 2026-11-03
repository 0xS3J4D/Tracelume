from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins

FIXTURES = Path(__file__).parent / "fixtures"


def test_bodyfile_parsing_flags_deleted_and_keeps_pipes() -> None:
    plugin = load_plugins(Path(__file__).parents[2])["sleuthkit"]
    arts = list(plugin.parse_output(RunContext(Path("/e"), FIXTURES, EvidenceKind.disk_image)))
    assert len(arts) == 3  # "." entry skipped
    plan, draft, folder = arts
    assert plan.data["status"] == "allocated" and plan.data["size"] == 42
    assert plan.timestamp == datetime(2024, 5, 1, 9, 15, 2, tzinfo=UTC)
    assert plan.data["crtime"] == "2024-05-01T09:15:00+00:00"
    assert draft.data["deleted"] is True
    assert draft.data["path"] == "/vol2048/Documents/secret|draft.docx"
    assert draft.title.startswith("[deleted] ")
    assert draft.data["atime"] is None
    assert folder.data["kind"] == "dir"
