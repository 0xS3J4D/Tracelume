from fastapi.testclient import TestClient


def test_dns_rebinding_host_rejected(client: TestClient) -> None:
    assert client.get("/api/cases", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/cases", headers={"Host": "127.0.0.1:8080"}).status_code == 200


def test_cross_site_write_blocked(client: TestClient) -> None:
    r = client.post(
        "/api/cases",
        json={"name": "x"},
        headers={"Origin": "https://evil.example", "Host": "127.0.0.1:8080"},
    )
    assert r.status_code == 403
    ok = client.post(
        "/api/cases",
        json={"name": "x"},
        headers={"Origin": "http://127.0.0.1:8080", "Host": "127.0.0.1:8080"},
    )
    assert ok.status_code == 201


def test_security_headers(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
