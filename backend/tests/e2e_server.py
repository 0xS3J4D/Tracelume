"""Backend for Playwright smoke tests: real API + DB, fake tool runner (no Docker).

The fake runner copies the synthetic ALEAPP fixture output, so the whole flow
(ingest -> verify -> run -> parse -> browse) is exercised without real evidence.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
tmp = Path(tempfile.mkdtemp(prefix="tracelume-e2e-"))
os.environ.update(
    TRACELUME_DATABASE_URL=f"sqlite:///{tmp}/e2e.db",
    TRACELUME_EVIDENCE_DIR=str(tmp / "evidence"),
    TRACELUME_WORKSPACE_DIR=str(tmp / "work"),
    TRACELUME_IMPORT_DIR=str(tmp / "import"),
    TRACELUME_PLUGINS_DIR=str(REPO / "plugins"),
    TRACELUME_JOB_QUEUE="inline",
    TRACELUME_RUNNER="fake",
)

import uvicorn  # noqa: E402

from tracelume import jobs  # noqa: E402

FIXTURE = REPO / "plugins/aleapp/tests/fixtures"


def fake(plugin, settings, ev_rel, out_rel, ctx, on_line):  # type: ignore[no-untyped-def]
    on_line(f"[fake] {' '.join(plugin.build_command(ctx))}")
    shutil.copytree(FIXTURE, settings.workspace_dir / out_rel, dirs_exist_ok=True)
    return 0


jobs.RUNNERS["fake"] = fake


def scripted_model(url, headers, payload):  # type: ignore[no-untyped-def]
    """Deterministic stand-in for a local LLM: one search, then a cited answer."""
    import json

    tool_msgs = [m for m in payload["messages"] if m["role"] == "tool"]
    if "max_tokens" in payload:
        return {"choices": [{"message": {"content": "OK"}}]}
    if not tool_msgs:
        call = {"id": "1", "type": "function", "function": {
            "name": "search_artifacts", "arguments": json.dumps({"types": ["message"]})}}
        return {"choices": [{"message": {"content": "", "tool_calls": [call]}}]}
    items = json.loads(tool_msgs[-1]["content"])["items"]
    lines = [f"- {i['title']} [a:{i['id']}]" for i in items[:3]]
    return {"choices": [{"message": {"content": "## Messages found\n" + "\n".join(lines)}}]}


from tracelume import assistant  # noqa: E402

assistant.TRANSPORT["http"] = scripted_model

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run("tracelume.main:app", host="127.0.0.1", port=port)
