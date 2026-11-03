"""Job orchestration: verify evidence, run tool, normalise output, record custody."""

import logging
import traceback
from collections.abc import Callable
from pathlib import Path

from sqlmodel import Session, select

from tracelume import audit
from tracelume.config import get_settings
from tracelume.db import get_engine
from tracelume.evidence import verify
from tracelume.models import Artifact, Evidence, Job, JobStatus, utcnow
from tracelume.plugins.base import RunContext
from tracelume.plugins.registry import get_plugin
from tracelume.plugins.runner import run_in_docker

Runner = Callable[..., int]
RUNNERS: dict[str, Runner] = {"docker": run_in_docker}
ACQUIRE_RUNNERS: dict[str, Callable[..., int]] = {}  # tests register fakes here
BATCH = 1000
CANCEL_MARK = "__cancel_requested__"


class CancelledError(Exception):
    pass


def job_dir(job_id: str) -> Path:
    return get_settings().workspace_dir / "jobs" / job_id


def log_path(job_id: str) -> Path:
    return job_dir(job_id) / "job.log"


def enqueue(job: Job) -> None:
    settings = get_settings()
    if settings.job_queue == "rq":
        from redis import Redis
        from rq import Queue

        Queue("tracelume", connection=Redis.from_url(settings.redis_url)).enqueue(
            execute_job, job.id, job_timeout=60 * 60 * 24
        )
    else:
        execute_job(job.id)


def execute_job(job_id: str) -> None:
    settings = get_settings()
    out_rel = f"jobs/{job_id}/output"
    out_dir = settings.workspace_dir / out_rel
    out_dir.mkdir(parents=True, exist_ok=True)
    logf = log_path(job_id).open("a", encoding="utf-8")

    def log(line: str) -> None:
        logf.write(line + "\n")
        logf.flush()

    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        if job is None:
            return
        actor = settings.examiner
        if job.plugin == "ios_acquire":
            logf.close()
            _execute_acquisition(job_id, out_rel, out_dir)
            return
        ev = s.get(Evidence, job.evidence_id)
        assert ev is not None
        if job.status == JobStatus.cancelled:
            log("[tracelume] job was cancelled before it started")
            logf.close()
            return
        job.status, job.started_at = JobStatus.running, utcnow()
        s.add(job)
        audit.record(
            s,
            actor,
            "job.start",
            case_id=job.case_id,
            object_type="job",
            object_id=job.id,
            details={"plugin": job.plugin},
        )
        try:
            log(f"[tracelume] verifying evidence {ev.original_filename} (sha256 {ev.sha256})")
            if not verify(s, ev, actor, reason=f"pre-job {job.id}"):
                raise RuntimeError(f"evidence integrity check failed: {ev.verify_status}")
            log("[tracelume] evidence hash verified")
            plugin = get_plugin(job.plugin)
            ctx = RunContext(
                evidence_path=Path("/evidence"),
                output_dir=out_dir,
                evidence_kind=ev.kind,
                params=job.params,
                log=logging.getLogger(f"tracelume.job.{job.id}"),
            )
            log(f"[tracelume] running {plugin.meta.tool_name} via image {plugin.image}")

            def is_cancelled() -> bool:
                with Session(get_engine()) as s2:
                    j = s2.get(Job, job_id)
                    return j is not None and j.error == CANCEL_MARK

            code = RUNNERS[settings.runner](
                plugin, settings, ev.stored_path, out_rel, ctx, log, is_cancelled
            )
            job.exit_code = code
            s.refresh(job)
            if job.error == CANCEL_MARK:
                raise CancelledError
            if code != 0:
                raise RuntimeError(f"tool exited with code {code}")
            log("[tracelume] parsing tool output")
            parse_ctx = RunContext(
                evidence_path=Path("/evidence"),
                output_dir=out_dir,
                evidence_kind=ev.kind,
                params=job.params,
            )
            count = 0
            for a in plugin.parse_output(parse_ctx):
                s.add(
                    Artifact(
                        case_id=job.case_id,
                        evidence_id=ev.id,
                        job_id=job.id,
                        type=a.type,
                        timestamp=a.timestamp,
                        timestamp_kind=a.timestamp_kind,
                        source_plugin=plugin.meta.name,
                        source_path=a.source_path,
                        title=a.title[:500],
                        data=a.data,
                    )
                )
                count += 1
                if count % BATCH == 0:
                    s.flush()
            job.artifact_count = count
            job.status = JobStatus.succeeded
            log(f"[tracelume] done: {count} artifacts")
        except CancelledError:
            s.rollback()
            fresh = s.get(Job, job_id)
            assert fresh is not None
            job = fresh
            job.status, job.error = JobStatus.cancelled, "cancelled by examiner"
            log("[tracelume] cancelled")
        except Exception as exc:  # noqa: BLE001 — any failure marks the job failed
            s.rollback()
            fresh = s.get(Job, job_id)
            assert fresh is not None
            job = fresh
            job.status, job.error = JobStatus.failed, str(exc)
            log(f"[tracelume] FAILED: {exc}")
            log(traceback.format_exc())
        finally:
            job.finished_at = utcnow()
            s.add(job)
            audit.record(
                s,
                actor,
                "job.finish",
                case_id=job.case_id,
                object_type="job",
                object_id=job.id,
                details={"status": job.status, "artifacts": job.artifact_count},
            )
            logf.close()


def counts_by_type(s: Session, case_id: str) -> dict[str, int]:
    from sqlalchemy import func

    rows = s.exec(
        select(Artifact.type, func.count())
        .where(Artifact.case_id == case_id)
        .group_by(Artifact.type)
    ).all()
    return {t: int(n) for t, n in rows}


def _execute_acquisition(job_id: str, out_rel: str, out_dir: Path) -> None:
    from tracelume import acquire
    from tracelume.evidence import ingest_stream
    from tracelume.models import EvidenceKind

    settings = get_settings()
    logf = log_path(job_id).open("a", encoding="utf-8")

    def log(line: str) -> None:
        logf.write(line + "\n")
        logf.flush()

    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        assert job is not None
        actor = str(job.params.get("actor") or settings.examiner)
        mode = job.params.get("mode", "list")
        udid = str(job.params.get("udid", ""))
        job.status, job.started_at = JobStatus.running, utcnow()
        s.add(job)
        audit.record(
            s,
            actor,
            "acquire.start",
            case_id=job.case_id,
            object_type="job",
            object_id=job.id,
            details={"mode": mode, "udid": udid},
        )

        def is_cancelled() -> bool:
            with Session(get_engine()) as s2:
                j = s2.get(Job, job_id)
                return j is not None and j.error == CANCEL_MARK

        try:
            argv = ["list"] if mode == "list" else ["backup", udid]
            runner = acquire.ACQ_RUNNER if not ACQUIRE_RUNNERS else ACQUIRE_RUNNERS["fake"]
            code = runner(settings, argv, out_rel, log, is_cancelled)
            job.exit_code = code
            s.refresh(job)
            if job.error == CANCEL_MARK:
                raise CancelledError
            if code != 0:
                raise RuntimeError(f"acquisition exited with code {code}")
            if mode == "backup":
                log("[tracelume] packaging backup and registering it as evidence")
                z = acquire.zip_backup(out_dir, udid)
                dev = acquire.device_info(out_dir)
                enc = (
                    (out_dir / "encryption.txt").read_text()
                    if (out_dir / "encryption.txt").exists()
                    else ""
                )
                notes = (
                    f"Logical backup over USB (idevicebackup2). Device: {dev.get('DeviceName')} "
                    f"{dev.get('ProductType')} iOS {dev.get('ProductVersion')}, serial "
                    f"{dev.get('SerialNumber')}, UDID {udid}. {enc.strip()}"
                )
                with z.open("rb") as f:
                    ev = ingest_stream(
                        s,
                        case_id=job.case_id,
                        actor=actor,
                        kind=EvidenceKind.ios_backup,
                        filename=z.name,
                        stream=f,
                        acquired_by=actor,
                        acquired_at=job.started_at,
                        notes=notes,
                    )
                z.unlink()
                job = s.get(Job, job_id) or job
                job.evidence_id = ev.id
                log(f"[tracelume] evidence registered: {ev.original_filename} sha256 {ev.sha256}")
            job.status = JobStatus.succeeded
        except CancelledError:
            s.rollback()
            job = s.get(Job, job_id) or job
            job.status, job.error = JobStatus.cancelled, "cancelled by examiner"
        except Exception as exc:  # noqa: BLE001
            s.rollback()
            job = s.get(Job, job_id) or job
            job.status, job.error = JobStatus.failed, str(exc)
            log(f"[tracelume] FAILED: {exc}")
        finally:
            job.finished_at = utcnow()
            s.add(job)
            audit.record(
                s,
                actor,
                "acquire.finish",
                case_id=job.case_id,
                object_type="job",
                object_id=job.id,
                details={"status": job.status, "evidence_id": job.evidence_id},
            )
            logf.close()
