"""Common plugin interface. See docs/writing-a-plugin.md."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, field_validator

from tracelume.models import EvidenceKind

ARTIFACT_TYPES = frozenset(
    {
        "message",
        "call",
        "contact",
        "location",
        "media",
        "web_history",
        "app_usage",
        "account",
        "file_entry",
        "process",
        "network_connection",
        "registry",
        "log_event",
        "database",
        "recovered_record",
        "event",
    }
)


class PluginMeta(BaseModel):
    name: str
    version: str
    description: str
    tool_name: str
    tool_version: str
    tool_license: str
    tool_url: str
    tool_authors: str


class ArtifactIn(BaseModel):
    """What a plugin emits. Validated before it is written to the case database."""

    type: str
    title: str
    timestamp: datetime | None = None
    timestamp_kind: str | None = None
    source_path: str | None = None
    data: dict[str, Any] = {}

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in ARTIFACT_TYPES:
            raise ValueError(f"unknown artifact type {v!r}")
        return v

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return v.astimezone(UTC)


@dataclass
class RunContext:
    evidence_path: Path  # path as seen by the tool (inside the container)
    output_dir: Path  # where the tool writes; host-side path for parse_output
    evidence_kind: EvidenceKind
    params: dict[str, Any] = field(default_factory=dict)
    log: logging.Logger = field(default_factory=lambda: logging.getLogger("tracelume.plugin"))


class Plugin(ABC):
    meta: ClassVar[PluginMeta]
    supported_evidence: ClassVar[frozenset[EvidenceKind]]
    image: ClassVar[str]  # docker image tag built from plugins/<name>/Dockerfile

    @abstractmethod
    def build_command(self, ctx: RunContext) -> list[str]:
        """CLI arguments run inside the tool image. Evidence is at /evidence (read-only),
        output must go to /output."""

    @abstractmethod
    def parse_output(self, ctx: RunContext) -> Iterable[ArtifactIn]:
        """Read tool output from ctx.output_dir and yield normalised artifacts."""
