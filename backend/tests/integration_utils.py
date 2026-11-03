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
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o777)
    proc = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
         "--security-opt", "no-new-privileges",
         "-v", f"{evidence.parent}:/evidence:ro", "-v", f"{output}:/output", image, *argv],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def have(tool: str) -> bool:
    return shutil.which(tool) is not None
