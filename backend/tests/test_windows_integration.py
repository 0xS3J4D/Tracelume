"""Real Windows-tool images on a public sample EVTX (CI only: needs Docker + internet)."""

import urllib.request
from pathlib import Path

import pytest

from tests.integration_utils import requires_docker, run_tool
from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins

SAMPLE = "https://raw.githubusercontent.com/omerbenamram/evtx/master/samples/security.evtx"
PLUGINS = Path(__file__).resolve().parents[2] / "plugins"


@pytest.fixture(scope="module")
def evtx(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("ev")
    path = d / "security.evtx"
    urllib.request.urlretrieve(SAMPLE, path)  # noqa: S310 (fixed https URL)
    return path


@requires_docker
@pytest.mark.parametrize("name", ["evtx", "hayabusa", "chainsaw"])
def test_windows_log_tools(name: str, evtx: Path, tmp_path: Path) -> None:
    plugin = load_plugins(PLUGINS)[name]
    out = tmp_path / "out"
    ctx = RunContext(Path("/evidence/security.evtx"), Path("/output"), EvidenceKind.logs)
    run_tool(plugin.image, plugin.build_command(ctx), evtx, out)
    arts = list(plugin.parse_output(RunContext(Path("/e"), out, EvidenceKind.logs)))
    if name == "evtx":
        assert len(arts) > 100 and all(a.timestamp for a in arts[:50])
    else:  # detections depend on the rule set; the run and parse must succeed
        assert all(a.type == "log_event" for a in arts)


@requires_docker
def test_yara_matches(tmp_path: Path) -> None:
    ev = tmp_path / "ev" / "notes.zip"
    ev.parent.mkdir()
    import zipfile

    with zipfile.ZipFile(ev, "w") as z:
        z.writestr("a/secret.txt", "the password is hunter2")
        z.writestr("b/other.txt", "nothing here")
    plugin = load_plugins(PLUGINS)["yara"]
    rules = 'rule Pw { strings: $a = "password" condition: $a }'
    ctx = RunContext(
        Path("/evidence/notes.zip"), Path("/output"), EvidenceKind.other, params={"rules": rules}
    )
    out = tmp_path / "out"
    run_tool(plugin.image, plugin.build_command(ctx), ev, out)
    (a,) = plugin.parse_output(RunContext(Path("/e"), out, EvidenceKind.other))
    assert a.data["file"].endswith("secret.txt")
