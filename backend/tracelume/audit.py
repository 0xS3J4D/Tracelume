"""Append-only, hash-chained audit log (chain of custody)."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, col, select

from tracelume.models import AuditLog, utcnow

GENESIS = "0" * 64


def _naive_utc(ts: datetime) -> str:
    # SQLite drops tzinfo on read; normalise so the hash is stable across backends.
    if ts.tzinfo is not None:
        ts = ts.astimezone(UTC).replace(tzinfo=None)
    return ts.isoformat()


def _canonical(entry: AuditLog) -> str:
    return json.dumps(
        {
            "ts": _naive_utc(entry.ts),
            "actor": entry.actor,
            "action": entry.action,
            "case_id": entry.case_id,
            "object_type": entry.object_type,
            "object_id": entry.object_id,
            "details": entry.details,
            "hash_before": entry.hash_before,
            "hash_after": entry.hash_after,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def compute_entry_hash(prev: str, entry: AuditLog) -> str:
    return hashlib.sha256((prev + _canonical(entry)).encode()).hexdigest()


def record(
    session: Session,
    actor: str,
    action: str,
    *,
    case_id: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    details: dict[str, Any] | None = None,
    hash_before: str | None = None,
    hash_after: str | None = None,
    commit: bool = True,
) -> AuditLog:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        # Serialise chain appends across processes.
        session.execute(text("SELECT pg_advisory_xact_lock(424242)"))
    last = session.exec(select(AuditLog).order_by(col(AuditLog.id).desc()).limit(1)).first()
    prev = last.entry_hash if last else GENESIS
    entry = AuditLog(
        ts=utcnow(),
        actor=actor,
        action=action,
        case_id=case_id,
        object_type=object_type,
        object_id=object_id,
        details=details or {},
        hash_before=hash_before,
        hash_after=hash_after,
        prev_entry_hash=prev,
        entry_hash="",
    )
    entry.entry_hash = compute_entry_hash(prev, entry)
    session.add(entry)
    if commit:
        session.commit()
        session.refresh(entry)
    else:
        session.flush()
    return entry


def verify_chain(session: Session) -> tuple[bool, int | None]:
    """Returns (ok, id of first broken entry)."""
    prev = GENESIS
    for entry in session.exec(select(AuditLog).order_by(col(AuditLog.id))):
        if entry.prev_entry_hash != prev or compute_entry_hash(prev, entry) != entry.entry_hash:
            return False, entry.id
        prev = entry.entry_hash
    return True, None
