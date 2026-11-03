import hashlib
import io
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tracelume import jobs

ALEAPP_FIXTURE = Path(__file__).resolve().parents[2] / "plugins/aleapp/tests/fixtures"
PAYLOAD = b"synthetic android dump - not real evidence\n" * 100


@pytest.fixture(autouse=True)
def fake_runner(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(plugin, settings, ev_rel, out_rel, ctx, on_line):  # type: ignore[no-untyped-def]
        calls.append(plugin.build_command(ctx))
        on_line("fake tool running")
        shutil.copytree(ALEAPP_FIXTURE, settings.workspace_dir / out_rel, dirs_exist_ok=True)
        return 0

    monkeypatch.setitem(jobs.RUNNERS, "fake", run)
    return calls


def _case(client: TestClient) -> str:
    r = client.post("/api/cases", json={"name": "Synthetic case"}, headers={"X-Examiner": "alice"})
    assert r.status_code == 201
    return str(r.json()["id"])


def _upload(client: TestClient, case_id: str) -> dict:  # type: ignore[type-arg]
    r = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("dump.zip", io.BytesIO(PAYLOAD))},
        data={"kind": "android_fs", "acquired_by": "alice"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def test_ingest_hashes_and_makes_read_only(client: TestClient, tmp_path: Path) -> None:
    case_id = _case(client)
    ev = _upload(client, case_id)
    assert ev["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert ev["md5"] == hashlib.md5(PAYLOAD).hexdigest()  # noqa: S324
    assert ev["size"] == len(PAYLOAD)
    stored = tmp_path / "evidence" / ev["stored_path"]
    assert stored.read_bytes() == PAYLOAD
    assert not os.access(stored, os.W_OK) or os.geteuid() == 0
    assert oct(stored.stat().st_mode & 0o777) == "0o444"


def test_aleapp_job_end_to_end(client: TestClient, fake_runner: list[list[str]]) -> None:
    case_id = _case(client)
    ev = _upload(client, case_id)
    r = client.post(
        f"/api/cases/{case_id}/jobs", json={"evidence_id": ev["id"], "plugin": "aleapp"}
    )
    assert r.status_code == 201, r.text
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "succeeded", job
    assert job["artifact_count"] == 6
    assert fake_runner[0][fake_runner[0].index("-i") + 1] == "/evidence"

    summary = client.get(f"/api/cases/{case_id}").json()
    assert summary["artifact_counts"]["message"] == 3

    page = client.get(f"/api/cases/{case_id}/artifacts", params={"type": "message"}).json()
    assert page["total"] == 3
    assert page["items"][0]["source_plugin"] == "aleapp"
    found = client.get(f"/api/cases/{case_id}/artifacts", params={"q": "synthetic"}).json()
    assert found["total"] == 1

    log = client.get(f"/api/jobs/{job['id']}/log").text
    assert "evidence hash verified" in log and "fake tool running" in log

    actions = [e["action"] for e in client.get(f"/api/cases/{case_id}/audit").json()]
    assert actions == [
        "case.create",
        "evidence.ingest",
        "job.create",
        "job.start",
        "evidence.verify",
        "job.finish",
    ]
    assert client.get("/api/audit/verify").json() == {"ok": True, "first_broken_id": None}


def test_tampered_evidence_blocks_job(
    client: TestClient, tmp_path: Path, fake_runner: list[list[str]]
) -> None:
    case_id = _case(client)
    ev = _upload(client, case_id)
    stored = tmp_path / "evidence" / ev["stored_path"]
    os.chmod(stored, 0o644)
    stored.write_bytes(PAYLOAD + b"x")
    r = client.post(
        f"/api/cases/{case_id}/jobs", json={"evidence_id": ev["id"], "plugin": "aleapp"}
    )
    job = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "failed"
    assert "integrity" in job["error"]
    assert fake_runner == []
    evs = client.get(f"/api/cases/{case_id}/evidence").json()
    assert evs[0]["verify_status"] == "mismatch"


def test_audit_chain_detects_tampering(client: TestClient) -> None:
    from sqlmodel import Session, select

    from tracelume.db import get_engine
    from tracelume.models import AuditLog

    _case(client)
    _case(client)
    with Session(get_engine()) as s:
        first = s.exec(select(AuditLog)).first()
        assert first is not None
        first.actor = "mallory"
        s.add(first)
        s.commit()
    assert client.get("/api/audit/verify").json()["ok"] is False


def test_rejects_unsupported_evidence_kind(client: TestClient) -> None:
    case_id = _case(client)
    r = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("mem.raw", io.BytesIO(b"mem"))},
        data={"kind": "memory_image"},
    )
    r = client.post(
        f"/api/cases/{case_id}/jobs", json={"evidence_id": r.json()["id"], "plugin": "aleapp"}
    )
    assert r.status_code == 400


def test_import_dir_rejects_traversal(client: TestClient) -> None:
    case_id = _case(client)
    r = client.post(
        f"/api/cases/{case_id}/evidence/import", json={"path": "../../etc/passwd", "kind": "other"}
    )
    assert r.status_code == 400
