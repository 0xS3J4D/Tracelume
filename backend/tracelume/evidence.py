"""Evidence ingest and verification. Originals are write-once, then read-only."""

import os
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from sqlmodel import Session

from tracelume import audit
from tracelume.config import get_settings
from tracelume.hashing import hash_file, hash_stream
from tracelume.models import Evidence, EvidenceKind, utcnow


class EvidenceError(Exception):
    pass


def _make_read_only(path: Path) -> None:
    ro = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    if path.is_dir():
        for root, dirs, files in os.walk(path):
            for f in files:
                os.chmod(Path(root) / f, ro)
            for d in dirs:
                os.chmod(Path(root) / d, ro | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)  # noqa: S103 (0o555)
    else:
        os.chmod(path, ro)


def ingest_stream(
    session: Session,
    *,
    case_id: str,
    actor: str,
    kind: EvidenceKind,
    filename: str,
    stream: BinaryIO,
    acquired_by: str | None = None,
    acquired_at: datetime | None = None,
    notes: str | None = None,
) -> Evidence:
    settings = get_settings()
    safe_name = Path(filename).name or "evidence.bin"
    ev = Evidence(
        case_id=case_id,
        kind=kind,
        original_filename=safe_name,
        stored_path="",
        size=0,
        sha256="",
        md5="",
        acquired_by=acquired_by,
        acquired_at=acquired_at,
        notes=notes,
    )
    rel = Path(case_id) / ev.id / safe_name
    dest = settings.evidence_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=False)
    with dest.open("xb") as out:
        h = hash_stream(stream, out)
    _make_read_only(dest)
    ev.stored_path, ev.size, ev.sha256, ev.md5 = str(rel), h.size, h.sha256, h.md5
    ev.last_verified_at = utcnow()
    session.add(ev)
    audit.record(
        session,
        actor,
        "evidence.ingest",
        case_id=case_id,
        object_type="evidence",
        object_id=ev.id,
        hash_after=ev.sha256,
        details={"filename": safe_name, "size": h.size, "md5": h.md5, "kind": kind},
        commit=False,
    )
    session.commit()
    session.refresh(ev)
    return ev


def ingest_from_import_dir(
    session: Session,
    *,
    case_id: str,
    actor: str,
    kind: EvidenceKind,
    relpath: str,
    acquired_by: str | None = None,
    notes: str | None = None,
) -> Evidence:
    """Register a large file already placed in the import directory (copied, never moved)."""
    settings = get_settings()
    base = settings.import_dir.resolve()
    src = (base / relpath).resolve()
    if not src.is_relative_to(base) or not src.is_file():
        raise EvidenceError("file not found in import directory")
    with src.open("rb") as f:
        return ingest_stream(
            session,
            case_id=case_id,
            actor=actor,
            kind=kind,
            filename=src.name,
            stream=f,
            acquired_by=acquired_by,
            notes=notes,
        )


def evidence_path(ev: Evidence) -> Path:
    return get_settings().evidence_dir / ev.stored_path


def verify(session: Session, ev: Evidence, actor: str, reason: str) -> bool:
    path = evidence_path(ev)
    if not path.exists():
        ev.verify_status = "missing"
        ok, sha = False, None
    else:
        h = hash_file(path)
        sha = h.sha256
        ok = h.sha256 == ev.sha256 and h.md5 == ev.md5
        ev.verify_status = "ok" if ok else "mismatch"
    ev.last_verified_at = utcnow()
    session.add(ev)
    audit.record(
        session,
        actor,
        "evidence.verify",
        case_id=ev.case_id,
        object_type="evidence",
        object_id=ev.id,
        hash_before=ev.sha256,
        hash_after=sha,
        details={"result": ev.verify_status, "reason": reason},
        commit=False,
    )
    session.commit()
    return ok


def remove_workspace(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
