import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import String, cast, func, or_
from sqlmodel import col, select

from tracelume import audit, evidence, jobs
from tracelume.api.deps import ActorDep, SessionDep
from tracelume.models import Artifact, AuditLog, Case, Evidence, EvidenceKind, Job, JobStatus
from tracelume.plugins.registry import get_plugin, load_plugins

router = APIRouter(prefix="/api")


# ---------- cases ----------
class CaseIn(BaseModel):
    name: str
    number: str | None = None
    description: str | None = None


class CaseSummary(BaseModel):
    case: Case
    evidence_count: int
    job_count: int
    artifact_count: int


@router.get("/cases")
def list_cases(s: SessionDep) -> list[Case]:
    return list(s.exec(select(Case).order_by(col(Case.created_at).desc())))


@router.post("/cases", status_code=201)
def create_case(body: CaseIn, s: SessionDep, actor: ActorDep) -> Case:
    if not body.name.strip():
        raise HTTPException(422, "name is required")
    c = Case(
        name=body.name.strip(), number=body.number, description=body.description, examiner=actor
    )
    s.add(c)
    audit.record(
        s,
        actor,
        "case.create",
        case_id=c.id,
        object_type="case",
        object_id=c.id,
        details=body.model_dump(),
        commit=False,
    )
    s.commit()
    s.refresh(c)
    return c


def _case(s: SessionDep, case_id: str) -> Case:
    c = s.get(Case, case_id)
    if c is None:
        raise HTTPException(404, "case not found")
    return c


@router.get("/cases/{case_id}")
def get_case(case_id: str, s: SessionDep) -> dict[str, Any]:
    c = _case(s, case_id)
    n_ev = s.exec(
        select(func.count()).select_from(Evidence).where(Evidence.case_id == case_id)
    ).one()
    n_job = s.exec(select(func.count()).select_from(Job).where(Job.case_id == case_id)).one()
    return {
        "case": c,
        "evidence_count": n_ev,
        "job_count": n_job,
        "artifact_counts": jobs.counts_by_type(s, case_id),
    }


# ---------- evidence ----------
@router.get("/cases/{case_id}/evidence")
def list_evidence(case_id: str, s: SessionDep) -> list[Evidence]:
    _case(s, case_id)
    return list(
        s.exec(
            select(Evidence).where(Evidence.case_id == case_id).order_by(col(Evidence.ingested_at))
        )
    )


@router.post("/cases/{case_id}/evidence", status_code=201)
def upload_evidence(
    case_id: str,
    s: SessionDep,
    actor: ActorDep,
    file: Annotated[UploadFile, File()],
    kind: Annotated[EvidenceKind, Form()],
    acquired_by: Annotated[str | None, Form()] = None,
    acquired_at: Annotated[datetime | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
) -> Evidence:
    _case(s, case_id)
    return evidence.ingest_stream(
        s,
        case_id=case_id,
        actor=actor,
        kind=kind,
        filename=file.filename or "evidence.bin",
        stream=file.file,
        acquired_by=acquired_by,
        acquired_at=acquired_at,
        notes=notes,
    )


class ImportIn(BaseModel):
    path: str
    kind: EvidenceKind
    acquired_by: str | None = None
    notes: str | None = None


@router.post("/cases/{case_id}/evidence/import", status_code=201)
def import_evidence(case_id: str, body: ImportIn, s: SessionDep, actor: ActorDep) -> Evidence:
    _case(s, case_id)
    try:
        return evidence.ingest_from_import_dir(
            s,
            case_id=case_id,
            actor=actor,
            kind=body.kind,
            relpath=body.path,
            acquired_by=body.acquired_by,
            notes=body.notes,
        )
    except evidence.EvidenceError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/evidence/{evidence_id}/verify")
def verify_evidence(evidence_id: str, s: SessionDep, actor: ActorDep) -> Evidence:
    ev = s.get(Evidence, evidence_id)
    if ev is None:
        raise HTTPException(404, "evidence not found")
    evidence.verify(s, ev, actor, reason="manual")
    s.refresh(ev)
    return ev


# ---------- plugins & jobs ----------
@router.get("/plugins")
def list_plugins() -> list[dict[str, Any]]:
    return [
        {
            **p.meta.model_dump(),
            "supported_evidence": sorted(p.supported_evidence),
            "image": p.image,
        }
        for p in load_plugins().values()
    ]


class JobIn(BaseModel):
    evidence_id: str
    plugin: str
    params: dict[str, Any] = {}


@router.post("/cases/{case_id}/jobs", status_code=201)
def create_job(case_id: str, body: JobIn, s: SessionDep, actor: ActorDep) -> Job:
    _case(s, case_id)
    ev = s.get(Evidence, body.evidence_id)
    if ev is None or ev.case_id != case_id:
        raise HTTPException(404, "evidence not found in case")
    try:
        plugin = get_plugin(body.plugin)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e
    if ev.kind not in plugin.supported_evidence:
        raise HTTPException(400, f"{plugin.meta.name} does not support {ev.kind}")
    job = Job(
        case_id=case_id,
        evidence_id=ev.id,
        plugin=plugin.meta.name,
        plugin_version=plugin.meta.version,
        params=body.params,
    )
    s.add(job)
    audit.record(
        s,
        actor,
        "job.create",
        case_id=case_id,
        object_type="job",
        object_id=job.id,
        details={"plugin": job.plugin, "evidence_id": ev.id},
        commit=False,
    )
    s.commit()
    s.refresh(job)
    jobs.job_dir(job.id).mkdir(parents=True, exist_ok=True)
    jobs.log_path(job.id).touch()
    jobs.enqueue(job)
    s.refresh(job)
    return job


@router.get("/cases/{case_id}/jobs")
def list_jobs(case_id: str, s: SessionDep) -> list[Job]:
    return list(
        s.exec(select(Job).where(Job.case_id == case_id).order_by(col(Job.created_at).desc()))
    )


@router.get("/jobs/{job_id}")
def get_job(job_id: str, s: SessionDep) -> Job:
    job = s.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job


@router.get("/jobs/{job_id}/log")
async def stream_log(job_id: str, s: SessionDep) -> StreamingResponse:
    """Server-sent events: one `data:` line per log line, then `event: end`."""
    if s.get(Job, job_id) is None:
        raise HTTPException(404, "job not found")
    path = jobs.log_path(job_id)

    async def gen() -> AsyncIterator[str]:
        from sqlmodel import Session

        from tracelume.db import get_engine

        pos = 0
        while True:
            if path.exists():
                with path.open("r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                for line in chunk.splitlines():
                    yield f"data: {line}\n\n"
            with Session(get_engine()) as s2:
                j = s2.get(Job, job_id)
                done = j is None or j.status in (
                    JobStatus.succeeded,
                    JobStatus.failed,
                    JobStatus.cancelled,
                )
            if done:
                yield "event: end\ndata: end\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------- artifacts ----------
class ArtifactPage(BaseModel):
    total: int
    items: list[Artifact]


@router.get("/cases/{case_id}/artifacts")
def list_artifacts(
    case_id: str,
    s: SessionDep,
    type: str | None = None,
    plugin: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(le=1000)] = 100,
    offset: int = 0,
) -> ArtifactPage:
    stmt = select(Artifact).where(Artifact.case_id == case_id)
    if type:
        stmt = stmt.where(Artifact.type == type)
    if plugin:
        stmt = stmt.where(Artifact.source_plugin == plugin)
    if since:
        stmt = stmt.where(col(Artifact.timestamp) >= since)
    if until:
        stmt = stmt.where(col(Artifact.timestamp) <= until)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(col(Artifact.title).ilike(like), cast(Artifact.data, String).ilike(like))
        )
    total = s.exec(select(func.count()).select_from(stmt.subquery())).one()
    items = s.exec(
        stmt.order_by(col(Artifact.timestamp).desc().nulls_last()).offset(offset).limit(limit)
    ).all()
    return ArtifactPage(total=total, items=list(items))


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, s: SessionDep) -> Artifact:
    a = s.get(Artifact, artifact_id)
    if a is None:
        raise HTTPException(404, "artifact not found")
    return a


# ---------- audit ----------
@router.get("/cases/{case_id}/audit")
def case_audit(case_id: str, s: SessionDep) -> list[AuditLog]:
    return list(
        s.exec(select(AuditLog).where(AuditLog.case_id == case_id).order_by(col(AuditLog.id)))
    )


@router.get("/audit/verify")
def verify_audit(s: SessionDep) -> dict[str, Any]:
    ok, broken = audit.verify_chain(s)
    return {"ok": ok, "first_broken_id": broken}
