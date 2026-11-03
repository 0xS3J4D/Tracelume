import hashlib
import io
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tracelume import jobs

BODY = Path(__file__).resolve().parents[2] / "plugins/sleuthkit/tests/fixtures/vol_2048.body"
CONTENT = b"recovered synthetic document"


def fake_tsk(plugin, settings, ev_rel, out_rel, ctx, on_line, *_):  # type: ignore[no-untyped-def]
    out = settings.workspace_dir / out_rel
    cmd = plugin.build_command(ctx)
    on_line(" ".join(cmd))
    if "extract" in cmd:
        rec = out / "recovered"
        rec.mkdir(parents=True)
        (rec / cmd[-1]).write_bytes(CONTENT)
        (rec / "recovered.json").write_text(
            json.dumps(
                {
                    "name": cmd[-1],
                    "inode": cmd[-2],
                    "offset": cmd[-3],
                    "size": len(CONTENT),
                    "sha256": hashlib.sha256(CONTENT).hexdigest(),
                }
            )
        )
    else:
        shutil.copy(BODY, out / "vol_2048.body")
    return 0


@pytest.fixture
def disk_case(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setitem(jobs.RUNNERS, "fake", fake_tsk)
    cid = client.post("/api/cases", json={"name": "Disk"}).json()["id"]
    ev = client.post(
        f"/api/cases/{cid}/evidence",
        files={"file": ("disk.dd", io.BytesIO(b"x" * 512))},
        data={"kind": "disk_image"},
    ).json()
    job = client.post(
        f"/api/cases/{cid}/jobs", json={"evidence_id": ev["id"], "plugin": "sleuthkit"}
    )
    assert client.get(f"/api/jobs/{job.json()['id']}").json()["status"] == "succeeded"
    return str(cid)


def test_recover_deleted_file_and_download(client: TestClient, disk_case: str) -> None:
    arts = client.get(f"/api/cases/{disk_case}/artifacts", params={"type": "file_entry"}).json()
    deleted = next(a for a in arts["items"] if a["data"]["deleted"])
    job = client.post(f"/api/artifacts/{deleted['id']}/recover")
    assert job.status_code == 201, job.text
    j = client.get(f"/api/jobs/{job.json()['id']}").json()
    assert j["status"] == "succeeded" and j["params"]["offset"] == "2048"
    rec = client.get(
        f"/api/cases/{disk_case}/artifacts", params={"q": "Recovered file content"}
    ).json()
    data = rec["items"][0]["data"]
    assert data["deleted"] is True and data["from_artifact"] == deleted["id"]
    f = client.get(f"/api/jobs/{j['id']}/files/{data['recovered_file']}")
    assert (
        f.content == CONTENT
        and f.headers["x-content-sha256"] == hashlib.sha256(CONTENT).hexdigest()
    )
    assert client.get(f"/api/jobs/{j['id']}/files/../../../etc/passwd").status_code == 404
    actions = [e["action"] for e in client.get(f"/api/cases/{disk_case}/audit").json()]
    assert "file.export" in actions


def test_recover_rejects_directories_and_injection(client: TestClient, disk_case: str) -> None:
    arts = client.get(f"/api/cases/{disk_case}/artifacts", params={"type": "file_entry"}).json()
    folder = next(a for a in arts["items"] if a["data"]["kind"] == "dir")
    assert client.post(f"/api/artifacts/{folder['id']}/recover").status_code == 400
    from tracelume.models import EvidenceKind
    from tracelume.plugins.base import RunContext
    from tracelume.plugins.registry import get_plugin

    with pytest.raises(ValueError):
        get_plugin("sleuthkit").build_command(
            RunContext(
                Path("/e/x"),
                Path("/o"),
                EvidenceKind.disk_image,
                params={"mode": "extract", "inode": "5; rm -rf /", "offset": "0"},
            )
        )


def test_cancel_queued_job(client: TestClient) -> None:
    from sqlmodel import Session

    from tracelume.db import get_engine
    from tracelume.models import Job, JobStatus

    cid = client.post("/api/cases", json={"name": "C"}).json()["id"]
    ev = client.post(
        f"/api/cases/{cid}/evidence",
        files={"file": ("a.zip", io.BytesIO(b"z"))},
        data={"kind": "android_fs"},
    ).json()
    with Session(get_engine()) as s:
        job = Job(case_id=cid, evidence_id=ev["id"], plugin="aleapp", plugin_version="0")
        s.add(job)
        s.commit()
        jid = job.id
    r = client.post(f"/api/jobs/{jid}/cancel")
    assert r.json()["status"] == JobStatus.cancelled
    jobs.execute_job(jid)  # a worker picking it up later must not run it
    assert client.get(f"/api/jobs/{jid}").json()["status"] == "cancelled"
    assert client.post(f"/api/jobs/{jid}/cancel").status_code == 409
