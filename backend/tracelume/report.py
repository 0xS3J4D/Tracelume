"""Case report export (HTML, PDF)."""

import base64
import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import Session, col, select

from tracelume import __version__, audit
from tracelume.jobs import counts_by_type
from tracelume.models import Artifact, ArtifactTag, AuditLog, Case, Evidence, Job, Note, Tag
from tracelume.plugins.registry import load_plugins

TEMPLATES = Path(__file__).parent / "templates"


def _utc(v: datetime | None) -> str:
    if v is None:
        return "—"
    v = v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)
    return v.strftime("%Y-%m-%d %H:%M:%S UTC")


def _bytes(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return str(n)


_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["j2"]))
_env.filters["utc"] = _utc
_env.filters["bytes"] = _bytes


def render_html(s: Session, case: Case, actor: str) -> str:
    ok, _ = audit.verify_chain(s)
    head = s.exec(select(AuditLog).order_by(col(AuditLog.id).desc()).limit(1)).first()
    evidence = list(s.exec(select(Evidence).where(Evidence.case_id == case.id)))
    jobs = list(s.exec(select(Job).where(Job.case_id == case.id).order_by(col(Job.created_at))))
    tags = list(s.exec(select(Tag).where(Tag.case_id == case.id).order_by(col(Tag.name))))
    tagged: list[tuple[Tag, list[Artifact]]] = []
    for t in tags:
        items = list(
            s.exec(
                select(Artifact)
                .join(ArtifactTag, col(ArtifactTag.artifact_id) == Artifact.id)
                .where(ArtifactTag.tag_id == t.id)
                .order_by(col(Artifact.timestamp))
            )
        )
        if items:
            tagged.append((t, items))
    notes = list(s.exec(select(Note).where(Note.case_id == case.id).order_by(col(Note.created_at))))
    by_artifact: dict[str, list[Note]] = defaultdict(list)
    for n in notes:
        if n.artifact_id:
            by_artifact[n.artifact_id].append(n)
    ctx: dict[str, Any] = {
        "case": case,
        "actor": actor,
        "version": __version__,
        "generated": _utc(datetime.now(UTC)),
        "chain_ok": ok,
        "chain_head": head.entry_hash[:16] if head else "—",
        "evidence": evidence,
        "ev_names": {e.id: e.original_filename for e in evidence},
        "jobs": jobs,
        "tools": {
            n: f"{p.meta.tool_name} {p.meta.tool_version}" for n, p in load_plugins().items()
        },
        "counts": sorted(counts_by_type(s, case.id).items(), key=lambda x: -x[1]),
        "tagged": tagged,
        "notes_by_artifact": by_artifact,
        "case_notes": [n for n in notes if not n.artifact_id],
        "audit": list(
            s.exec(select(AuditLog).where(AuditLog.case_id == case.id).order_by(col(AuditLog.id)))
        ),
        "logo": base64.b64encode((TEMPLATES / "logo.svg").read_bytes()).decode(),
    }
    return _env.get_template("report.html.j2").render(**ctx)


def render_pdf(html: str) -> bytes:
    from weasyprint import HTML

    return bytes(HTML(string=html).write_pdf())


def export(s: Session, case: Case, actor: str, fmt: str) -> tuple[bytes, str]:
    html = render_html(s, case, actor)
    data = render_pdf(html) if fmt == "pdf" else html.encode()
    digest = hashlib.sha256(data).hexdigest()
    audit.record(
        s,
        actor,
        "report.export",
        case_id=case.id,
        object_type="case",
        object_id=case.id,
        hash_after=digest,
        details={"format": fmt},
    )
    return data, digest
