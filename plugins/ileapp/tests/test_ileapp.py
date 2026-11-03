from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins

FIXTURES = Path(__file__).parent / "fixtures"


def _plugin():  # type: ignore[no-untyped-def]
    return load_plugins(Path(__file__).parents[2])["ileapp"]


def test_fs_zip_command() -> None:
    ctx = RunContext(Path("/evidence/ffs.zip"), Path("/output"), EvidenceKind.ios_fs)
    cmd = _plugin().build_command(ctx)
    assert cmd[cmd.index("-t") + 1] == "zip"


def test_zipped_backup_unpacks_into_workspace() -> None:
    ctx = RunContext(Path("/evidence/backup.zip"), Path("/output"), EvidenceKind.ios_backup)
    cmd = _plugin().build_command(ctx)
    assert cmd[0] == "sh" and "-t itunes" in cmd[2]
    assert cmd[-3:] == ["/evidence/backup.zip", "/output/_backup", "/output"]


def test_parse() -> None:
    ctx = RunContext(Path("/evidence"), FIXTURES, EvidenceKind.ios_fs)
    arts = {a.type: a for a in _plugin().parse_output(ctx)}
    assert arts["message"].timestamp == datetime(2024, 6, 10, 7, 30, tzinfo=UTC)
    assert arts["app_usage"].data["Bundle ID"] == "com.apple.MobileSMS"
