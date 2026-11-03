import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_workspace import populated  # noqa: F401  (fixture)
from tracelume import assistant


class FakeModel:
    """Scripted OpenAI-compatible model: searches, then answers citing what it found."""

    def __init__(self, fake_citation: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fake_citation = fake_citation

    def __call__(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append({"url": url, "payload": payload})
        msgs = payload["messages"]
        tool_msgs = [m for m in msgs if m["role"] == "tool"]
        if not tool_msgs:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_artifacts",
                                        "arguments": json.dumps(
                                            {"query": "synthetic", "types": ["message"]}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        found = json.loads(tool_msgs[-1]["content"])["items"]
        cite = f"[a:{found[0]['id']}]"
        bogus = " [a:00000000-0000-0000-0000-000000000000]" if self.fake_citation else ""
        return {"choices": [{"message": {"content": f"One message mentions it {cite}.{bogus}"}}]}


def test_assistant_uses_tools_and_cites(
    client: TestClient,
    populated: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeModel(fake_citation=True)
    monkeypatch.setitem(assistant.TRANSPORT, "http", model)
    r = client.post(f"/api/cases/{populated}/assistant", json={"question": "Any synthetic texts?"})
    assert r.status_code == 200, r.text
    reply = r.json()
    assert reply["steps"][0]["tool"] == "search_artifacts"
    assert len(reply["citations"]) == 1
    assert "citation removed" in reply["content"]  # hallucinated id is stripped
    assert model.calls[0]["url"] == "http://ollama:11434/v1/chat/completions"
    assert "Artifact counts" in model.calls[0]["payload"]["messages"][0]["content"]
    history = client.get(f"/api/cases/{populated}/assistant/messages").json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    log = client.get(f"/api/cases/{populated}/audit").json()
    entry = next(e for e in log if e["action"] == "assistant.ask")
    assert entry["details"]["endpoint_local"] is True
    assert entry["details"]["tools"] == ["search_artifacts"]


def test_remote_endpoint_requires_case_opt_in(
    client: TestClient,
    populated: str,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(assistant.TRANSPORT, "http", FakeModel())
    s = client.put(
        "/api/settings/assistant",
        json={"base_url": "https://api.example.com/v1", "api_key": "sk-secret"},
    ).json()
    assert s["local"] is False and s["api_key"] == "••••"
    r = client.post(f"/api/cases/{populated}/assistant", json={"question": "hi"})
    assert r.status_code == 400 and "not local" in r.json()["detail"]
    client.put(f"/api/cases/{populated}/assistant/policy", json={"allow_remote": True})
    r = client.post(f"/api/cases/{populated}/assistant", json={"question": "plan"})
    assert r.status_code == 200
    assert client.get("/api/settings").json()["assistant"]["api_key"] == "••••"
    assert "sk-secret" not in json.dumps(client.get(f"/api/cases/{populated}/audit").json())


def test_tools_are_case_scoped(client: TestClient, populated: str) -> None:  # noqa: F811
    from sqlmodel import Session

    from tracelume.db import get_engine
    from tracelume.models import Artifact, Case

    other = client.post("/api/cases", json={"name": "Other"}).json()["id"]
    with Session(get_engine()) as s:
        art = s.query(Artifact).filter(Artifact.case_id == populated).first()  # type: ignore[attr-defined]
        tools = assistant.CaseTools(s, s.get(Case, other))  # type: ignore[arg-type]
        assert tools.get_artifact(art.id) == {"error": "no such artifact in this case"}
        assert tools.search_artifacts(query="synthetic")["total_matches"] == 0
        assert "error" in tools.sql_query("x:y", "SELECT 1")
