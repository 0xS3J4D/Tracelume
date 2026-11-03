"""Real ALEAPP run on the synthetic Android dump."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

from tests.integration_utils import requires_docker, run_tool
from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins

REPO = Path(__file__).resolve().parents[3]


@requires_docker
def test_aleapp_parses_synthetic_sms(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("mk", REPO / "scripts/make_synthetic_android.py")
    assert spec and spec.loader
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    dump = mk.build(tmp_path / "ev" / "synthetic-android.zip")

    plugin = load_plugins(REPO / "plugins")["aleapp"]
    out = tmp_path / "out"
    ctx = RunContext(
        Path("/evidence/synthetic-android.zip"),
        Path("/output"),
        EvidenceKind.android_fs,
    )
    run_tool(plugin.image, plugin.build_command(ctx), dump, out)
    msgs = [
        a
        for a in plugin.parse_output(RunContext(Path("/e"), out, EvidenceKind.android_fs))
        if a.type == "message"
    ]
    assert len(msgs) == 3
    assert min(m.timestamp for m in msgs if m.timestamp) == datetime(
        2024, 5, 1, 9, 15, 2, tzinfo=UTC
    )
