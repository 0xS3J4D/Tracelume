"""Database tables. All timestamps are timezone-aware UTC."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

JsonType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


class EvidenceKind(StrEnum):
    disk_image = "disk_image"
    android_fs = "android_fs"
    ios_backup = "ios_backup"
    ios_fs = "ios_fs"
    memory_image = "memory_image"
    logs = "logs"
    other = "other"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Case(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    number: str | None = None
    description: str | None = None
    examiner: str
    status: str = "open"
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Evidence(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    kind: EvidenceKind
    original_filename: str
    stored_path: str  # relative to evidence_dir
    size: int
    sha256: str
    md5: str
    acquired_by: str | None = None
    acquired_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    notes: str | None = None
    ingested_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    last_verified_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    verify_status: str = "ok"  # ok | mismatch | missing


class Job(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    evidence_id: str = Field(foreign_key="evidence.id", index=True)
    plugin: str
    plugin_version: str
    params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JsonType))
    status: JobStatus = JobStatus.queued
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    started_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    finished_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    exit_code: int | None = None
    artifact_count: int = 0
    error: str | None = None


class Artifact(SQLModel, table=True):
    __table_args__ = (
        Index("ix_artifact_case_type", "case_id", "type"),
        Index("ix_artifact_case_ts", "case_id", "timestamp"),
    )
    id: str = Field(default_factory=_uuid, primary_key=True)
    case_id: str = Field(foreign_key="case.id")
    evidence_id: str = Field(foreign_key="evidence.id")
    job_id: str = Field(foreign_key="job.id", index=True)
    type: str
    timestamp: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    timestamp_kind: str | None = None
    source_plugin: str
    source_path: str | None = None
    title: str
    data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JsonType))


class AuditLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    actor: str
    action: str
    case_id: str | None = Field(default=None, index=True)
    object_type: str | None = None
    object_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JsonType))
    hash_before: str | None = None
    hash_after: str | None = None
    prev_entry_hash: str
    entry_hash: str


class Tag(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    name: str
    color: str = "#f59e0b"


class ArtifactTag(SQLModel, table=True):
    artifact_id: str = Field(foreign_key="artifact.id", primary_key=True)
    tag_id: str = Field(foreign_key="tag.id", primary_key=True)
    tagged_by: str
    tagged_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Note(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    case_id: str = Field(foreign_key="case.id", index=True)
    artifact_id: str | None = Field(default=None, foreign_key="artifact.id", index=True)
    author: str
    body: str
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
