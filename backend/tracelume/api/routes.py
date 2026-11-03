import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
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


def _open_case(s: SessionDep, case_id: str) -> Case:
    c = _case(s, case_id)
    if c.status == "closed":
        raise HTTPException(409, "case is closed — reopen it to add evidence or run analyses")
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
    _open_case(s, case_id)
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
    _open_case(s, case_id)
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
    _open_case(s, case_id)
    ev = s.get(Evidence, body.evidence_id)
    if ev is None or ev.case_id != case_id:
        raise HTTPException(404, "evidence not found in case")
    try:
        plugin = get_plugin(body.plugin)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e
    if ev.kind not in plugin.supported_evidence:
        raise HTTPException(400, f"{plugin.meta.name} does not support {ev.kind}")
    for key, spec in plugin.params_schema.items():
        if spec.get("required") and not str(body.params.get(key, "")).strip():
            raise HTTPException(422, f"parameter '{key}' is required")
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


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, s: SessionDep, actor: ActorDep) -> Job:
    job = s.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    if job.status == JobStatus.queued:
        job.status, job.error = JobStatus.cancelled, "cancelled by examiner"
    elif job.status == JobStatus.running:
        job.error = jobs.CANCEL_MARK  # picked up by the worker within seconds
    else:
        raise HTTPException(409, f"job is already {job.status}")
    s.add(job)
    audit.record(
        s,
        actor,
        "job.cancel",
        case_id=job.case_id,
        object_type="job",
        object_id=job.id,
        commit=False,
    )
    s.commit()
    s.refresh(job)
    return job


@router.get("/jobs/{job_id}/files/{path:path}")
def job_file(job_id: str, path: str, s: SessionDep, actor: ActorDep) -> FileResponse:
    """Download a file produced by a job (e.g. recovered file content). Audit-logged."""
    import hashlib

    job = s.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    base = (jobs.job_dir(job_id) / "output").resolve()
    target = (base / path).resolve()
    if not target.is_relative_to(base) or not target.is_file():
        raise HTTPException(404, "file not found")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    audit.record(
        s,
        actor,
        "file.export",
        case_id=job.case_id,
        object_type="job",
        object_id=job_id,
        hash_after=digest,
        details={"path": path},
    )
    return FileResponse(
        target,
        filename=target.name,
        media_type="application/octet-stream",
        headers={"X-Content-SHA256": digest},
    )


@router.post("/artifacts/{artifact_id}/recover", status_code=201)
def recover_file(artifact_id: str, s: SessionDep, actor: ActorDep) -> Job:
    """Recover a file's content from a disk image (Sleuth Kit icat), incl. deleted files."""
    a = s.get(Artifact, artifact_id)
    if a is None or a.source_plugin != "sleuthkit" or a.type != "file_entry":
        raise HTTPException(400, "only Sleuth Kit file entries can be recovered")
    d = a.data
    if d.get("kind") != "file" or "inode" not in d:
        raise HTTPException(400, "not a regular file")
    offset = str(d.get("volume", "vol_0")).removeprefix("vol_")
    params = {
        "mode": "extract",
        "inode": d["inode"],
        "offset": offset,
        "name": str(d.get("path", "file")).rsplit("/", 1)[-1] or "file",
        "path": d.get("path"),
        "deleted": d.get("deleted", False),
        "artifact_id": a.id,
    }
    return create_job(
        a.case_id, JobIn(evidence_id=a.evidence_id, plugin="sleuthkit", params=params), s, actor
    )


@router.get("/jobs/{job_id}/thumbs/{name}")
def job_thumb(job_id: str, name: str) -> FileResponse:
    """Thumbnails generated by the media plugin (derived previews, not evidence exports)."""
    import re

    if not re.fullmatch(r"[0-9a-f]{64}\.jpg", name):
        raise HTTPException(404, "not found")
    path = jobs.job_dir(job_id) / "output" / "thumbs" / name
    if not path.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"}
    )


class CasePatch(BaseModel):
    name: str | None = None
    number: str | None = None
    description: str | None = None
    status: str | None = None  # open | closed


@router.patch("/cases/{case_id}")
def update_case(case_id: str, body: CasePatch, s: SessionDep, actor: ActorDep) -> Case:
    c = _case(s, case_id)
    patch = body.model_dump(exclude_none=True)
    if "status" in patch and patch["status"] not in ("open", "closed"):
        raise HTTPException(422, "status must be open or closed")
    if "name" in patch and not patch["name"].strip():
        raise HTTPException(422, "name is required")
    before = c.model_dump(mode="json")
    for k, v in patch.items():
        setattr(c, k, v.strip() if isinstance(v, str) else v)
    s.add(c)
    audit.record(
        s,
        actor,
        "case.update",
        case_id=case_id,
        object_type="case",
        object_id=case_id,
        details={"changes": {k: [before.get(k), v] for k, v in patch.items()}},
        commit=False,
    )
    s.commit()
    s.refresh(c)
    return c


@router.get("/cases/{case_id}/export.zip")
def export_case(case_id: str, s: SessionDep, actor: ActorDep) -> Response:
    from datetime import UTC, datetime

    from tracelume.export import build_bundle

    c = _case(s, case_id)
    data = build_bundle(s, c, actor)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in c.name)[:60]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Response(
        data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="tracelume-case-{safe}-{stamp}.zip"'
        },
    )


# ---------- iPhone acquisition (Linux + USB) ----------
@router.get("/acquire/status")
def acquire_status() -> dict[str, Any]:
    from tracelume.config import get_settings

    return {"usb_available": get_settings().usb_acquisition}


class AcquireIn(BaseModel):
    mode: str = "list"  # list | backup
    udid: str | None = None


@router.post("/cases/{case_id}/acquire/ios", status_code=201)
def acquire_ios(case_id: str, body: AcquireIn, s: SessionDep, actor: ActorDep) -> Job:
    import re

    from tracelume.config import get_settings

    _open_case(s, case_id)
    if not get_settings().usb_acquisition:
        raise HTTPException(
            400,
            "USB acquisition is only available when Tracelume runs on a "
            "Linux host (start it with ./tracelume start)",
        )
    if body.mode not in ("list", "backup"):
        raise HTTPException(422, "mode must be list or backup")
    if body.mode == "backup" and not re.fullmatch(r"[0-9A-Fa-f-]{24,40}", body.udid or ""):
        raise HTTPException(422, "a valid device id (UDID) is required")
    job = Job(
        case_id=case_id,
        evidence_id=None,
        plugin="ios_acquire",
        plugin_version="0.1.0",
        params={"mode": body.mode, "udid": body.udid, "actor": actor},
    )
    s.add(job)
    audit.record(
        s,
        actor,
        "acquire.create",
        case_id=case_id,
        object_type="job",
        object_id=job.id,
        details={"mode": body.mode, "udid": body.udid},
        commit=False,
    )
    s.commit()
    s.refresh(job)
    jobs.job_dir(job.id).mkdir(parents=True, exist_ok=True)
    jobs.log_path(job.id).touch()
    jobs.enqueue(job)
    s.refresh(job)
    return job


@router.get("/jobs/{job_id}/devices")
def acquire_devices(job_id: str) -> list[dict[str, Any]]:
    import json

    p = jobs.job_dir(job_id) / "output" / "devices.json"
    return json.loads(p.read_text()) if p.exists() else []
