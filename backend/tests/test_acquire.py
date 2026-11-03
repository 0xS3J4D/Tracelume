import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from tracelume import jobs

UDID = "00008110-001A2B3C4D5E801E"


def fake_phone(settings, argv, out_rel, on_line, cancelled):  # type: ignore[no-untyped-def]
    out = settings.workspace_dir / out_rel
    if argv[0] == "list":
        (out / "devices.json").write_text(
            json.dumps(
                [
                    {
                        "udid": UDID,
                        "DeviceName": "Demo iPhone",
                        "ProductVersion": "18.1",
                        "paired": True,
                    }
                ]
            )
        )
        return 0
    b = out / "backup" / argv[1]
    b.mkdir(parents=True)
    (b / "Manifest.db").write_bytes(b"SQLite format 3\x00synthetic")
    (b / "Info.plist").write_text("<plist/>")
    (out / "device.json").write_text(
        json.dumps(
            {
                "DeviceName": "Demo iPhone",
                "ProductType": "iPhone15,2",
                "ProductVersion": "18.1",
                "SerialNumber": "SYNTHETIC",
            }
        )
    )
    (out / "encryption.txt").write_text("Backup encryption is OFF.")
    on_line("Backup Successful.")
    return 0


@pytest.fixture
def usb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRACELUME_USB_ACQUISITION", "1")
    from tracelume.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setitem(jobs.ACQUIRE_RUNNERS, "fake", fake_phone)


def test_disabled_without_usb(client: TestClient) -> None:
    cid = client.post("/api/cases", json={"name": "A"}).json()["id"]
    assert client.get("/api/acquire/status").json() == {"usb_available": False}
    assert client.post(f"/api/cases/{cid}/acquire/ios", json={"mode": "list"}).status_code == 400


def test_list_and_backup_registers_evidence(client: TestClient, usb: None) -> None:
    cid = client.post("/api/cases", json={"name": "A"}).json()["id"]
    j = client.post(f"/api/cases/{cid}/acquire/ios", json={"mode": "list"}).json()
    assert client.get(f"/api/jobs/{j['id']}/devices").json()[0]["udid"] == UDID

    bad = client.post(f"/api/cases/{cid}/acquire/ios", json={"mode": "backup", "udid": "x; rm"})
    assert bad.status_code == 422
    j = client.post(f"/api/cases/{cid}/acquire/ios", json={"mode": "backup", "udid": UDID}).json()
    j = client.get(f"/api/jobs/{j['id']}").json()
    assert j["status"] == "succeeded", j
    ev = client.get(f"/api/cases/{cid}/evidence").json()
    assert len(ev) == 1 and ev[0]["kind"] == "ios_backup" and ev[0]["id"] == j["evidence_id"]
    assert "Demo iPhone" in ev[0]["notes"] and len(ev[0]["sha256"]) == 64
    from tracelume.config import get_settings

    stored = get_settings().evidence_dir / ev[0]["stored_path"]
    with zipfile.ZipFile(stored) as z:
        assert f"{UDID}/Manifest.db" in z.namelist()
    actions = [e["action"] for e in client.get(f"/api/cases/{cid}/audit").json()]
    assert {"acquire.create", "acquire.start", "evidence.ingest", "acquire.finish"} <= set(actions)
