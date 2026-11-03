import io
import json
import zipfile

from fastapi.testclient import TestClient

from tests.test_workspace import populated  # noqa: F401


def test_close_reopen_and_export(client: TestClient, populated: str) -> None:  # noqa: F811
    r = client.patch(f"/api/cases/{populated}", json={"status": "closed", "number": "N-7"})
    assert r.json()["status"] == "closed" and r.json()["number"] == "N-7"
    blocked = client.post(
        f"/api/cases/{populated}/evidence",
        files={"file": ("x.bin", io.BytesIO(b"x"))},
        data={"kind": "other"},
    )
    assert blocked.status_code == 409
    client.patch(f"/api/cases/{populated}", json={"status": "open"})

    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/cases/{populated}/export.zip").content))
    names = set(z.namelist())
    assert {
        "report.html",
        "report.pdf",
        "artifacts.csv",
        "artifacts.jsonl",
        "audit_log.json",
        "evidence.json",
        "manifest.json",
        "SHA256SUMS",
    } <= names
    import hashlib

    for line in z.read("SHA256SUMS").decode().splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256(z.read(name)).hexdigest() == digest
    assert len(z.read("artifacts.jsonl").splitlines()) == 6
    manifest = json.loads(z.read("manifest.json"))
    assert list(manifest["evidence_hashes"].values())[0]["sha256"]
    actions = [e["action"] for e in client.get(f"/api/cases/{populated}/audit").json()]
    assert "case.update" in actions and "case.export" in actions
