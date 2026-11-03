import io

import pytest
from fastapi.testclient import TestClient

from tests.test_core import PAYLOAD, fake_runner  # noqa: F401  (fixture re-export)


@pytest.fixture
def populated(client: TestClient) -> str:
    case_id = client.post("/api/cases", json={"name": "WS case"}).json()["id"]
    ev = client.post(f"/api/cases/{case_id}/evidence",
                     files={"file": ("dump.zip", io.BytesIO(PAYLOAD))},
                     data={"kind": "android_fs"}).json()
    job = client.post(f"/api/cases/{case_id}/jobs",
                      json={"evidence_id": ev["id"], "plugin": "aleapp"}).json()
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    return str(case_id)


def test_histogram(client: TestClient, populated: str) -> None:
    h = client.get(f"/api/cases/{populated}/timeline/histogram", params={"buckets": 10}).json()
    assert len(h["buckets"]) == 10
    assert sum(b["count"] for b in h["buckets"]) == 4  # 3 messages + 1 location have times
    assert h["min"].startswith("2024-05-01T09:15:02")
    only_loc = client.get(f"/api/cases/{populated}/timeline/histogram",
                          params={"type": "location"}).json()
    assert sum(b["count"] for b in only_loc["buckets"]) == 1


def test_artifact_filters(client: TestClient, populated: str) -> None:
    r = client.get(f"/api/cases/{populated}/artifacts",
                   params=[("type", "message"), ("type", "location"), ("order", "asc")]).json()
    assert r["total"] == 4
    assert r["items"][0]["timestamp"].startswith("2024-05-01T09:15:02")
    r = client.get(f"/api/cases/{populated}/artifacts",
                   params={"since": "2024-05-02T00:00:00Z"}).json()
    assert r["total"] == 1


def test_global_search(client: TestClient, populated: str) -> None:
    hits = client.get("/api/search", params={"q": "synthetic fixture"}).json()
    assert len(hits) == 1 and hits[0]["case_name"] == "WS case"


def test_tags_notes_and_report(client: TestClient, populated: str) -> None:
    art = client.get(f"/api/cases/{populated}/artifacts", params={"type": "message"}).json()
    aid = art["items"][0]["id"]
    tag = client.post(f"/api/cases/{populated}/tags", json={"name": "Key evidence"}).json()
    assert client.put(f"/api/artifacts/{aid}/tags/{tag['id']}").status_code == 204
    assert client.put(f"/api/artifacts/{aid}/tags/{tag['id']}").status_code == 204  # idempotent
    tags = client.get(f"/api/cases/{populated}/tags").json()
    assert tags[0]["count"] == 1
    tagged = client.get(f"/api/cases/{populated}/artifacts", params={"tag": tag["id"]}).json()
    assert tagged["total"] == 1

    client.post(f"/api/cases/{populated}/notes", json={"body": "Matches witness statement",
                                                        "artifact_id": aid})
    client.post(f"/api/cases/{populated}/notes", json={"body": "General <b>note</b>"})
    assert len(client.get(f"/api/cases/{populated}/notes").json()) == 2

    r = client.get(f"/api/cases/{populated}/report.html")
    assert r.status_code == 200
    html = r.text
    assert "Key evidence" in html and "Matches witness statement" in html
    assert "General &lt;b&gt;note&lt;/b&gt;" in html  # escaped
    assert "intact" in html
    pdf = client.get(f"/api/cases/{populated}/report.pdf")
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.headers["X-Report-SHA256"]) == 64

    actions = [e["action"] for e in client.get(f"/api/cases/{populated}/audit").json()]
    assert {"tag.create", "artifact.tag", "note.create", "report.export"} <= set(actions)
    assert client.get("/api/audit/verify").json()["ok"] is True
