from datetime import UTC, datetime
from pathlib import Path

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins

FIXTURES = Path(__file__).parent / "fixtures"


def _plugin():  # type: ignore[no-untyped-def]
    return load_plugins(Path(__file__).parents[2])["aleapp"]


def _ctx(out: Path) -> RunContext:
    return RunContext(
        evidence_path=Path("/evidence/dump.zip"),
        output_dir=out,
        evidence_kind=EvidenceKind.android_fs,
    )


def test_command_uses_readonly_mounts_and_input_type() -> None:
    cmd = _plugin().build_command(_ctx(Path("/output")))
    assert cmd[cmd.index("-t") + 1] == "zip"
    assert cmd[cmd.index("-i") + 1] == "/evidence/dump.zip"
    assert cmd[cmd.index("-o") + 1] == "/output"


def test_parse_output_maps_types_and_utc() -> None:
    arts = list(_plugin().parse_output(_ctx(FIXTURES)))
    by_type: dict[str, list] = {}  # type: ignore[type-arg]
    for a in arts:
        by_type.setdefault(a.type, []).append(a)
    # repeated header block is skipped, bookkeeping file ignored
    assert len(by_type["message"]) == 3
    assert len(by_type["location"]) == 1
    assert "event" in by_type  # Settings Secure -> generic
    assert all(a.data.get("module") != "_Staged files SHA-256" for a in arts)

    first = by_type["message"][0]
    assert first.timestamp == datetime(2024, 5, 1, 9, 15, 2, tzinfo=UTC)
    assert first.title == "SMS messages: Hello from the synthetic fixture"
    assert first.source_path.endswith("mmssms.db")
    offset = by_type["message"][2]
    assert offset.timestamp == datetime(2024, 5, 2, 16, 0, tzinfo=UTC)

    loc = by_type["location"][0]
    assert loc.data["Timestamp"] == "2024-05-01 10:00:00"  # typed header cleaned
    assert loc.timestamp is not None
