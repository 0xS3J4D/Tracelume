"""Case assistant: an LLM that answers questions by querying the case through read-only tools.

Design rules
- Local-first: the default endpoint is an Ollama server on the internal network. A non-local
  endpoint is refused unless the examiner has allowed remote processing for that case.
- The model never sees the whole case. It calls tools (search, fetch, SQL) whose inputs and
  outputs are shown to the examiner, and it must cite artifact IDs for every claim.
- Everything is read-only, and every exchange is written to the audit log.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import String, cast, func, or_
from sqlmodel import Session, col, select

from tracelume import audit, settings_store, sqlbench
from tracelume.jobs import counts_by_type
from tracelume.models import Artifact, ArtifactTag, Case, Evidence, Job, JobStatus, Tag

MAX_STEPS = 8
CITE = re.compile(r"\[a:([0-9a-f-]{36})\]")

SYSTEM = """You are the analysis assistant inside Tracelume, a digital forensics workbench.
You help a qualified examiner investigate ONE case. Rules:
1. Base every factual statement on data returned by your tools. Never invent artifacts,
   names, numbers or times. If the tools return nothing relevant, say so plainly.
2. Cite evidence inline as [a:<artifact id>] right after the statement it supports.
3. All timestamps are UTC. Say "UTC" when you give a time.
4. Distinguish facts (what the data shows) from interpretation (what it might mean), and
   flag carved/recovered records as lower confidence.
5. Be concise and structured. Use short headings and bullet lists for plans and summaries.
6. Answer in the language the examiner writes in.
7. You cannot modify anything. Suggest next steps (searches, filters, SQL) when useful.
Case: {case_name} ({case_number}). Evidence: {evidence}. Artifact counts: {counts}."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "case_overview",
            "description": "Counts by artifact type and by source module, evidence items, tags, "
            "and the time range of the case.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_artifacts",
            "description": "Search artifacts. Full-text over title and content; filter by type, "
            "tag name and UTC time range. Returns up to `limit` (max 50), newest first "
            "unless order='asc'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "words to find (optional)"},
                    "types": {"type": "array", "items": {"type": "string"}},
                    "module": {
                        "type": "string",
                        "description": "source module, e.g. 'SMS messages'",
                    },
                    "tag": {"type": "string"},
                    "since": {"type": "string", "description": "ISO 8601 UTC"},
                    "until": {"type": "string", "description": "ISO 8601 UTC"},
                    "order": {"type": "string", "enum": ["asc", "desc"]},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_artifact",
            "description": "Full record of one artifact by id.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_databases",
            "description": "SQLite databases extracted from the evidence, with tables, row counts "
            "and recovered (deleted) record counts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sql_query",
            "description": "Run ONE read-only SQLite SELECT on an extracted database (use the id "
            "from list_databases). Returns at most 50 rows.",
            "parameters": {
                "type": "object",
                "properties": {"db_id": {"type": "string"}, "sql": {"type": "string"}},
                "required": ["db_id", "sql"],
            },
        },
    },
]

PRESETS = {
    "plan": "Look at the case overview and propose a structured investigation plan: the key "
    "questions to answer, which artifact types and sources to review first, specific "
    "searches/filters/SQL to run, and what to verify manually. Use a checklist.",
    "summary": "Summarise what this case contains so far: evidence, processing, the most "
    "significant activity and the time span, with citations.",
    "deleted": "What deleted or recovered data is there in this case (deleted files, recovered "
    "SQLite records)? Summarise the most relevant items with citations and explain "
    "the confidence of each source.",
}


class AssistantError(Exception):
    pass


def _clip(v: Any, n: int) -> Any:
    s = json.dumps(v, default=str, ensure_ascii=False)
    return v if len(s) <= n else s[:n] + "…"


def _art(a: Artifact, data_chars: int = 500) -> dict[str, Any]:
    return {
        "id": a.id,
        "type": a.type,
        "time_utc": a.timestamp.isoformat() if a.timestamp else None,
        "title": a.title,
        "plugin": a.source_plugin,
        "source_path": a.source_path,
        "data": _clip(a.data, data_chars),
    }


class CaseTools:
    def __init__(self, s: Session, case: Case):
        self.s, self.case = s, case
        self.seen: set[str] = set()

    def _sqlite_jobs(self) -> list[str]:
        return [
            j.id
            for j in self.s.exec(
                select(Job).where(
                    Job.case_id == self.case.id,
                    Job.plugin == "sqlite_recover",
                    Job.status == JobStatus.succeeded,
                )
            )
        ]

    def case_overview(self) -> dict[str, Any]:
        s, cid = self.s, self.case.id
        module = (
            func.json_extract(Artifact.data, "$.module")
            if s.get_bind().dialect.name == "sqlite"
            else Artifact.data["module"].as_string()
        )
        modules = s.execute(
            select(module, func.count())
            .where(Artifact.case_id == cid)
            .group_by(module)
            .order_by(func.count().desc())
            .limit(60)
        ).all()
        lo, hi = s.execute(
            select(func.min(Artifact.timestamp), func.max(Artifact.timestamp)).where(
                Artifact.case_id == cid
            )
        ).one()
        return {
            "counts_by_type": counts_by_type(s, cid),
            "top_modules": {str(m): int(n) for m, n in modules if m},
            "time_range_utc": [lo.isoformat() if lo else None, hi.isoformat() if hi else None],
            "evidence": [
                {"file": e.original_filename, "kind": e.kind, "sha256": e.sha256}
                for e in s.exec(select(Evidence).where(Evidence.case_id == cid))
            ],
            "tags": [t.name for t in s.exec(select(Tag).where(Tag.case_id == cid))],
        }

    def search_artifacts(
        self,
        query: str | None = None,
        types: list[str] | None = None,
        module: str | None = None,
        tag: str | None = None,
        since: str | None = None,
        until: str | None = None,
        order: str = "desc",
        limit: int = 20,
    ) -> dict[str, Any]:
        stmt = select(Artifact).where(Artifact.case_id == self.case.id)
        if types:
            stmt = stmt.where(col(Artifact.type).in_(types))
        for word in (query or "").split()[:6]:
            like = f"%{word}%"
            stmt = stmt.where(
                or_(col(Artifact.title).ilike(like), cast(Artifact.data, String).ilike(like))
            )
        if module:
            stmt = stmt.where(cast(Artifact.data, String).ilike(f"%{module}%"))
        if tag:
            stmt = (
                stmt.join(ArtifactTag, col(ArtifactTag.artifact_id) == Artifact.id)
                .join(Tag, col(Tag.id) == ArtifactTag.tag_id)
                .where(col(Tag.name).ilike(tag))
            )
        if since:
            stmt = stmt.where(col(Artifact.timestamp) >= datetime.fromisoformat(since))
        if until:
            stmt = stmt.where(col(Artifact.timestamp) <= datetime.fromisoformat(until))
        total = self.s.exec(select(func.count()).select_from(stmt.subquery())).one()
        ts = col(Artifact.timestamp)
        stmt = stmt.order_by(ts.asc().nulls_last() if order == "asc" else ts.desc().nulls_last())
        rows = self.s.exec(stmt.limit(max(1, min(int(limit), 50)))).all()
        self.seen.update(a.id for a in rows)
        return {"total_matches": total, "returned": len(rows), "items": [_art(a) for a in rows]}

    def get_artifact(self, id: str) -> dict[str, Any]:
        a = self.s.get(Artifact, id)
        if a is None or a.case_id != self.case.id:
            return {"error": "no such artifact in this case"}
        self.seen.add(a.id)
        return _art(a, 4000)

    def list_databases(self) -> list[dict[str, Any]]:
        return [
            {
                "db_id": r.id,
                "path": r.path,
                "tables": {n: t.get("rows") for n, t in list(r.tables.items())[:40]},
                "recovered": r.recovered,
            }
            for r in sqlbench.list_databases(self._sqlite_jobs())[:80]
        ]

    def sql_query(self, db_id: str, sql: str) -> dict[str, Any]:
        try:
            ref = sqlbench.resolve(db_id, self._sqlite_jobs())
            res = sqlbench.run_query(ref, sql)
        except sqlbench.SqlError as e:
            return {"error": str(e)}
        return {
            "columns": res["columns"],
            "rows": [_clip(r, 400) for r in res["rows"][:50]],
            "truncated": res["truncated"] or len(res["rows"]) > 50,
        }

    def call(self, name: str, args: dict[str, Any]) -> Any:
        table: dict[str, Callable[..., Any]] = {
            "case_overview": self.case_overview,
            "search_artifacts": self.search_artifacts,
            "get_artifact": self.get_artifact,
            "list_databases": self.list_databases,
            "sql_query": self.sql_query,
        }
        fn = table.get(name)
        if fn is None:
            return {"error": f"unknown tool {name}"}
        try:
            return fn(**args)
        except (TypeError, ValueError) as e:
            return {"error": f"bad arguments: {e}"}


Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


def http_transport(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    try:
        r = httpx.post(url, headers=headers, json=payload, timeout=300)
    except httpx.HTTPError as e:
        raise AssistantError(
            f"cannot reach the model server ({e.__class__.__name__}). "
            "Is the AI profile running? See docs/assistant.md"
        ) from e
    if r.status_code >= 400:
        raise AssistantError(f"model server error {r.status_code}: {r.text[:300]}")
    return dict(r.json())


TRANSPORT: dict[str, Transport] = {"http": http_transport}  # replaced in tests


def remote_allowed(s: Session, case_id: str) -> bool:
    return bool(settings_store.get(s, f"case:{case_id}:assistant").get("allow_remote"))


def ask(
    s: Session, case: Case, actor: str, history: list[dict[str, str]], question: str
) -> dict[str, Any]:
    cfg = settings_store.get(s, "assistant")
    if not cfg.get("enabled"):
        raise AssistantError("the assistant is disabled in Settings")
    local = settings_store.is_local(cfg["base_url"])
    if not local and not remote_allowed(s, case.id):
        raise AssistantError(
            "the configured model endpoint is not local. Allow remote "
            "processing for this case first (case data would leave this machine)"
        )
    tools = CaseTools(s, case)
    ov = tools.case_overview()
    system = SYSTEM.format(
        case_name=case.name,
        case_number=case.number or "no number",
        evidence=", ".join(f"{e['file']} ({e['kind']})" for e in ov["evidence"]) or "none",
        counts=json.dumps(ov["counts_by_type"]),
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    messages += [
        {"role": m["role"], "content": m["content"]}
        for m in history[-10:]
        if m.get("role") in ("user", "assistant")
    ]
    messages.append({"role": "user", "content": PRESETS.get(question, question)})
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    steps: list[dict[str, Any]] = []
    answer = ""
    for _ in range(MAX_STEPS):
        resp = TRANSPORT["http"](
            url,
            headers,
            {
                "model": cfg["model"],
                "messages": messages,
                "tools": TOOLS,
                "temperature": cfg.get("temperature", 0.1),
            },
        )
        msg = resp["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            answer = msg.get("content") or ""
            break
        messages.append(
            {"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls}
        )
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.call(name, args if isinstance(args, dict) else {})
            steps.append({"tool": name, "args": args, "result": _clip(result, 3000)})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": c.get("id", name),
                    "content": json.dumps(result, default=str, ensure_ascii=False)[:12000],
                }
            )
    else:
        answer = "I stopped after the maximum number of steps. Try a narrower question."
    # keep only citations that point at real artifacts of this case
    cited = list(dict.fromkeys(CITE.findall(answer)))
    valid = (
        {
            a
            for (a,) in s.execute(
                select(Artifact.id).where(Artifact.case_id == case.id, col(Artifact.id).in_(cited))
            )
        }
        if cited
        else set()
    )
    for bad in set(cited) - valid:
        answer = answer.replace(f"[a:{bad}]", "[citation removed: not in case]")
    audit.record(
        s,
        actor,
        "assistant.ask",
        case_id=case.id,
        object_type="case",
        object_id=case.id,
        hash_after=hashlib.sha256(answer.encode()).hexdigest(),
        details={
            "model": cfg["model"],
            "endpoint_local": local,
            "question": question[:2000],
            "tools": [st["tool"] for st in steps],
            "citations": len(valid),
        },
    )
    return {
        "answer": answer,
        "steps": steps,
        "citations": [c for c in cited if c in valid],
        "model": cfg["model"],
        "local": local,
    }
