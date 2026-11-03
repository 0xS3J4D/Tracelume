"""Helpers for integration tests that run real tool images (opt-in: TRACELUME_INTEGRATION=1)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

requires_docker = pytest.mark.skipif(
    os.environ.get("TRACELUME_INTEGRATION") != "1", reason="set TRACELUME_INTEGRATION=1"
)


def run_tool(image: str, argv: list[str], evidence: Path, output: Path) -> str:
    """Run like the worker does: no network, read-only evidence, dropped capabilities."""
    registry = os.environ.get("TRACELUME_REGISTRY", "ghcr.io/0xs3j4d")
    image = f"{registry}/{image}" if registry else image
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o777)
    # Tool images run as an unprivileged user; make the evidence readable like the app stores it.
    evidence.parent.chmod(0o755)
    if evidence.is_file():
        evidence.chmod(0o644)
    proc = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
         "--security-opt", "no-new-privileges",
         "-v", f"{evidence.parent}:/evidence:ro", "-v", f"{output}:/output", image, *argv],
        capture_output=True, text=True, check=False, timeout=1200,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def have(tool: str) -> bool:
    return shutil.which(tool) is not None
