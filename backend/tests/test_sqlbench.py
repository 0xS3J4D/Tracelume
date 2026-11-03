import io
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tracelume import jobs

CARVER = Path(__file__).resolve().parents[2] / "plugins/sqlite_recover/sqlite_carve.py"


@pytest.fixture
def case_with_db(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db = tmp_path / "src" / "chat.db"
    db.parent.mkdir()
    con = sqlite3.connect(db)
    con.execute("PRAGMA secure_delete=OFF")
    con.execute("CREATE TABLE msg (id INTEGER PRIMARY KEY, body TEXT)")
    con.executemany("INSERT INTO msg VALUES (?, ?)", [(i, f"hello {i}") for i in range(50)])
    con.commit()
    con.execute("DELETE FROM msg WHERE id = 3")
    con.commit()
    con.close()

    def run(plugin, settings, ev_rel, out_rel, ctx, on_line):  # type: ignore[no-untyped-def]
        src = settings.evidence_dir / ev_rel
        subprocess.run(
            [sys.executable, "-I", str(CARVER), str(src), str(settings.workspace_dir / out_rel)],
            check=True,
        )
        return 0

    monkeypatch.setitem(jobs.RUNNERS, "fake", run)
    case_id = client.post("/api/cases", json={"name": "SQL"}).json()["id"]
    ev = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("chat.db", io.BytesIO(db.read_bytes()))},
        data={"kind": "other"},
    ).json()
    job = client.post(
        f"/api/cases/{case_id}/jobs", json={"evidence_id": ev["id"], "plugin": "sqlite_recover"}
    ).json()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    shutil.rmtree(db.parent)
    return str(case_id)


def test_recovered_record_artifact(client: TestClient, case_with_db: str) -> None:
    r = client.get(
        f"/api/cases/{case_with_db}/artifacts", params={"type": "recovered_record"}
    ).json()
    assert any("hello 3" in a["title"] for a in r["items"])


def test_workbench_read_only(client: TestClient, case_with_db: str) -> None:
    dbs = client.get(f"/api/cases/{case_with_db}/databases").json()
    assert len(dbs) == 1 and dbs[0]["tables"] == {"msg": 49}
    url = f"/api/cases/{case_with_db}/databases/{dbs[0]['id']}"
    schema = client.get(f"{url}/schema").json()
    assert schema[0]["columns"][1]["name"] == "body"

    ok = client.post(f"{url}/query", json={"sql": "SELECT body FROM msg ORDER BY id LIMIT 2"})
    assert ok.json()["rows"] == [["hello 0"], ["hello 1"]]
    for bad in (
        "DELETE FROM msg",
        "DROP TABLE msg",
        "ATTACH DATABASE '/tmp/x' AS x",
        "SELECT 1; DELETE FROM msg",
        "PRAGMA writable_schema=1",
        "INSERT INTO msg VALUES (99,'x')",
    ):
        r = client.post(f"{url}/query", json={"sql": bad})
        assert r.status_code == 400, bad
    slow = client.post(
        f"{url}/query",
        json={
            "sql": (
                "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) "
                "SELECT count(*) FROM c"
            )
        },
    )
    assert slow.status_code == 400 and "timed out" in slow.json()["detail"]
    assert client.post(f"{url}/query", json={"sql": "SELECT count(*) FROM msg"}).json()["rows"] == [
        [49]
    ]
    audit = [e["action"] for e in client.get(f"/api/cases/{case_with_db}/audit").json()]
    assert audit.count("sql.query") >= 8


def test_cannot_reach_other_cases_db(client: TestClient, case_with_db: str) -> None:
    dbs = client.get(f"/api/cases/{case_with_db}/databases").json()
    other = client.post("/api/cases", json={"name": "Other"}).json()["id"]
    r = client.post(f"/api/cases/{other}/databases/{dbs[0]['id']}/query", json={"sql": "SELECT 1"})
    assert r.status_code == 404
