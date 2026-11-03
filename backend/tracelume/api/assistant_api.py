from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import col, select

from tracelume import assistant, audit, settings_store
from tracelume.api.deps import ActorDep, SessionDep
from tracelume.models import AssistantMessage, Case

router = APIRouter(prefix="/api")


# ---------- settings ----------
def _public(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        **cfg,
        "api_key": "••••" if cfg.get("api_key") else "",
        "local": settings_store.is_local(cfg.get("base_url", "")),
    }


@router.get("/settings")
def get_settings_all(s: SessionDep) -> dict[str, Any]:
    return {
        "assistant": _public(settings_store.get(s, "assistant")),
        "examiner": settings_store.get(s, "examiner"),
    }


class AssistantSettingsIn(BaseModel):
    enabled: bool | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None  # "••••" keeps the stored key
    temperature: float | None = None


@router.put("/settings/assistant")
def put_assistant(body: AssistantSettingsIn, s: SessionDep, actor: ActorDep) -> dict[str, Any]:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if patch.get("api_key") == "••••":
        patch.pop("api_key")
    cfg = settings_store.put(s, "assistant", patch)
    audit.record(
        s,
        actor,
        "settings.assistant",
        object_type="settings",
        details={k: ("set" if k == "api_key" else v) for k, v in patch.items()},
    )
    return _public(cfg)


class ExaminerIn(BaseModel):
    name: str


@router.put("/settings/examiner")
def put_examiner(body: ExaminerIn, s: SessionDep, actor: ActorDep) -> dict[str, Any]:
    cfg = settings_store.put(s, "examiner", {"name": body.name.strip()[:100]})
    audit.record(s, actor, "settings.examiner", object_type="settings", details=cfg)
    return cfg


@router.post("/settings/assistant/test")
def test_assistant(s: SessionDep) -> dict[str, Any]:
    cfg = settings_store.get(s, "assistant")
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    try:
        r = assistant.TRANSPORT["http"](
            url,
            headers,
            {
                "model": cfg["model"],
                "max_tokens": 5,
                "messages": [{"role": "user", "content": "Reply with OK."}],
            },
        )
        return {"ok": True, "reply": r["choices"][0]["message"].get("content", "")[:100]}
    except (assistant.AssistantError, KeyError, IndexError) as e:
        return {"ok": False, "error": str(e)}


# ---------- per-case policy and chat ----------
class PolicyIn(BaseModel):
    allow_remote: bool


@router.get("/cases/{case_id}/assistant/policy")
def get_policy(case_id: str, s: SessionDep) -> dict[str, Any]:
    cfg = settings_store.get(s, "assistant")
    return {
        "allow_remote": assistant.remote_allowed(s, case_id),
        "endpoint_local": settings_store.is_local(cfg["base_url"]),
        "model": cfg["model"],
        "enabled": cfg["enabled"],
    }


@router.put("/cases/{case_id}/assistant/policy")
def put_policy(case_id: str, body: PolicyIn, s: SessionDep, actor: ActorDep) -> dict[str, Any]:
    settings_store.put(s, f"case:{case_id}:assistant", {"allow_remote": body.allow_remote})
    audit.record(
        s,
        actor,
        "assistant.policy",
        case_id=case_id,
        object_type="case",
        object_id=case_id,
        details={"allow_remote": body.allow_remote},
    )
    return get_policy(case_id, s)


@router.get("/cases/{case_id}/assistant/messages")
def messages(case_id: str, s: SessionDep) -> list[AssistantMessage]:
    return list(
        s.exec(
            select(AssistantMessage)
            .where(AssistantMessage.case_id == case_id)
            .order_by(col(AssistantMessage.created_at))
        )
    )


class AskIn(BaseModel):
    question: str


@router.post("/cases/{case_id}/assistant")
def ask(case_id: str, body: AskIn, s: SessionDep, actor: ActorDep) -> AssistantMessage:
    case = s.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    q = body.question.strip()
    if not q:
        raise HTTPException(422, "empty question")
    history = [{"role": m.role, "content": m.content} for m in messages(case_id, s)]
    try:
        res = assistant.ask(s, case, actor, history, q)
    except assistant.AssistantError as e:
        raise HTTPException(400, str(e)) from e
    label = {
        "plan": "Suggest an investigation plan",
        "summary": "Summarise the case",
        "deleted": "What deleted or recovered data is there?",
    }.get(q, q)
    s.add(AssistantMessage(case_id=case_id, role="user", content=label, author=actor))
    reply = AssistantMessage(
        case_id=case_id,
        role="assistant",
        content=res["answer"],
        steps=res["steps"],
        citations=res["citations"],
        model=res["model"],
        author=actor,
    )
    s.add(reply)
    s.commit()
    s.refresh(reply)
    return reply
