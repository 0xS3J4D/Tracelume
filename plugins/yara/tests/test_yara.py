import base64
from pathlib import Path

import pytest

from tracelume.models import EvidenceKind
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import load_plugins


def _p():  # type: ignore[no-untyped-def]
    return load_plugins(Path(__file__).parents[2])["yara"]


def test_rules_are_passed_safely() -> None:
    rules = 'rule x { strings: $a = "; rm -rf /" condition: $a }'
    cmd = _p().build_command(
        RunContext(
            Path("/evidence/d.img"),
            Path("/output"),
            EvidenceKind.disk_image,
            params={"rules": rules},
        )
    )
    assert base64.b64decode(cmd[-1]).decode() == rules
    with pytest.raises(ValueError):
        _p().build_command(RunContext(Path("/e"), Path("/o"), EvidenceKind.other, params={}))


def test_parse() -> None:
    (a,) = _p().parse_output(
        RunContext(Path("/e"), Path(__file__).parent / "fixtures", EvidenceKind.other)
    )
    assert a.title == "YARA Demo matched data/x.txt" and a.data["strings"][0]["offset"] == 16
