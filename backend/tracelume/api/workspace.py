"""Timeline, search, tags and notes."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import Float, String, cast, func, or_
from sqlmodel import col, select
from sqlmodel.sql.expression import SelectOfScalar

from tracelume import audit
from tracelume.api.deps import ActorDep, SessionDep
from tracelume.models import Artifact, ArtifactTag, Case, Note, Tag

router = APIRouter(prefix="/api")


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _filtered(
    case_id: str,
    types: list[str] | None,
    plugins: list[str] | None,
    q: str | None,
    tag: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> SelectOfScalar[Artifact]:
    stmt = select(Artifact).where(Artifact.case_id == case_id)
    if types:
        stmt = stmt.where(col(Artifact.type).in_(types))
    if plugins:
        stmt = stmt.where(col(Artifact.source_plugin).in_(plugins))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(col(Artifact.title).ilike(like), cast(Artifact.data, String).ilike(like))
        )
    if since:
        stmt = stmt.where(col(Artifact.timestamp) >= since)
    if until:
        stmt = stmt.where(col(Artifact.timestamp) <= until)
    if tag:
        stmt = stmt.join(ArtifactTag, col(ArtifactTag.artifact_id) == Artifact.id).where(
            ArtifactTag.tag_id == tag
        )
    return stmt


# ---------- artifacts ----------
class ArtifactPage(BaseModel):
    total: int
    items: list[Artifact]


@router.get("/cases/{case_id}/artifacts")
def list_artifacts(
    case_id: str,
    s: SessionDep,
    type: Annotated[list[str] | None, Query()] = None,
    plugin: Annotated[list[str] | None, Query()] = None,
    q: str | None = None,
    tag: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    order: str = "desc",
    limit: Annotated[int, Query(le=1000)] = 100,
    offset: int = 0,
) -> ArtifactPage:
    stmt = _filtered(case_id, type, plugin, q, tag, since, until)
    total = s.exec(select(func.count()).select_from(stmt.subquery())).one()
    ts = col(Artifact.timestamp)
    ordering = ts.asc().nulls_last() if order == "asc" else ts.desc().nulls_last()
    items = s.exec(stmt.order_by(ordering, col(Artifact.id)).offset(offset).limit(limit)).all()
    return ArtifactPage(total=total, items=list(items))


# ---------- timeline ----------
class Bucket(BaseModel):
    start: datetime
    end: datetime
    count: int
    by_type: dict[str, int]


class Histogram(BaseModel):
    min: datetime | None
    max: datetime | None
    buckets: list[Bucket]


@router.get("/cases/{case_id}/timeline/histogram")
def histogram(
    case_id: str,
    s: SessionDep,
    type: Annotated[list[str] | None, Query()] = None,
    plugin: Annotated[list[str] | None, Query()] = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    buckets: Annotated[int, Query(ge=1, le=500)] = 120,
) -> Histogram:
    base = _filtered(case_id, type, plugin, q).where(col(Artifact.timestamp).is_not(None))
    sub = base.subquery()
    lo, hi = s.exec(select(func.min(sub.c.timestamp), func.max(sub.c.timestamp))).one()
    if lo is None or hi is None:
        return Histogram(min=None, max=None, buckets=[])
    lo, hi = _aware(lo), _aware(hi)
    full_lo, full_hi = lo, hi
    if since:
        lo = max(lo, _aware(since))
    if until:
        hi = min(hi, _aware(until))
    if hi <= lo:
        hi = lo + timedelta(seconds=1)
    lo_s, span = lo.timestamp(), max((hi - lo).total_seconds(), 1.0)
    width = span / buckets
    dialect = s.get_bind().dialect.name
    ts = col(Artifact.timestamp)
    epoch: Any
    if dialect == "postgresql":
        epoch = func.extract("epoch", ts)
    else:
        epoch = cast(func.strftime("%s", ts), Float)
    idx = func.floor((epoch - lo_s) / width)
    stmt = (
        base.where(ts >= lo, ts <= hi)
        .with_only_columns(idx.label("b"), col(Artifact.type), func.count())
        .group_by("b", col(Artifact.type))
    )
    counts: dict[int, dict[str, int]] = {}
    for b, t, n in s.execute(stmt).all():
        i = min(int(b), buckets - 1)
        counts.setdefault(i, {})
        counts[i][t] = counts[i].get(t, 0) + int(n)
    out = [
        Bucket(
            start=lo + timedelta(seconds=i * width),
            end=lo + timedelta(seconds=(i + 1) * width),
            count=sum(counts.get(i, {}).values()),
            by_type=counts.get(i, {}),
        )
        for i in range(buckets)
    ]
    return Histogram(min=full_lo, max=full_hi, buckets=out)


# ---------- global search ----------
class SearchHit(BaseModel):
    artifact: Artifact
    case_name: str


@router.get("/search")
def global_search(
    s: SessionDep, q: Annotated[str, Query(min_length=2)], limit: Annotated[int, Query(le=200)] = 50
) -> list[SearchHit]:
    like = f"%{q}%"
    rows = s.exec(
        select(Artifact, Case.name)
        .join(Case, col(Case.id) == Artifact.case_id)
        .where(or_(col(Artifact.title).ilike(like), cast(Artifact.data, String).ilike(like)))
        .order_by(col(Artifact.timestamp).desc())
        .limit(limit)
    ).all()
    return [SearchHit(artifact=a, case_name=n) for a, n in rows]


# ---------- tags ----------
class TagIn(BaseModel):
    name: str
    color: str = "#f59e0b"


@router.get("/cases/{case_id}/tags")
def list_tags(case_id: str, s: SessionDep) -> list[dict[str, Any]]:
    rows = s.exec(
        select(Tag, func.count(col(ArtifactTag.artifact_id)))
        .outerjoin(ArtifactTag, col(ArtifactTag.tag_id) == Tag.id)
        .where(Tag.case_id == case_id)
        .group_by(col(Tag.id))
        .order_by(col(Tag.name))
    ).all()
    return [{**t.model_dump(), "count": int(n)} for t, n in rows]


@router.post("/cases/{case_id}/tags", status_code=201)
def create_tag(case_id: str, body: TagIn, s: SessionDep, actor: ActorDep) -> Tag:
    name = body.name.strip()[:60]
    if not name:
        raise HTTPException(422, "name required")
    existing = s.exec(select(Tag).where(Tag.case_id == case_id, Tag.name == name)).first()
    if existing:
        return existing
    t = Tag(case_id=case_id, name=name, color=body.color)
    s.add(t)
    audit.record(
        s,
        actor,
        "tag.create",
        case_id=case_id,
        object_type="tag",
        object_id=t.id,
        details={"name": name},
        commit=False,
    )
    s.commit()
    s.refresh(t)
    return t


@router.get("/artifacts/{artifact_id}/tags")
def artifact_tags(artifact_id: str, s: SessionDep) -> list[Tag]:
    return list(
        s.exec(
            select(Tag)
            .join(ArtifactTag, col(ArtifactTag.tag_id) == Tag.id)
            .where(ArtifactTag.artifact_id == artifact_id)
        )
    )


@router.put("/artifacts/{artifact_id}/tags/{tag_id}", status_code=204)
def add_tag(artifact_id: str, tag_id: str, s: SessionDep, actor: ActorDep) -> None:
    a, t = s.get(Artifact, artifact_id), s.get(Tag, tag_id)
    if a is None or t is None or a.case_id != t.case_id:
        raise HTTPException(404, "artifact or tag not found")
    if s.get(ArtifactTag, (artifact_id, tag_id)) is None:
        s.add(ArtifactTag(artifact_id=artifact_id, tag_id=tag_id, tagged_by=actor))
        audit.record(
            s,
            actor,
            "artifact.tag",
            case_id=a.case_id,
            object_type="artifact",
            object_id=artifact_id,
            details={"tag": t.name},
            commit=False,
        )
        s.commit()


@router.delete("/artifacts/{artifact_id}/tags/{tag_id}", status_code=204)
def remove_tag(artifact_id: str, tag_id: str, s: SessionDep, actor: ActorDep) -> None:
    link = s.get(ArtifactTag, (artifact_id, tag_id))
    t = s.get(Tag, tag_id)
    if link and t:
        s.delete(link)
        audit.record(
            s,
            actor,
            "artifact.untag",
            case_id=t.case_id,
            object_type="artifact",
            object_id=artifact_id,
            details={"tag": t.name},
            commit=False,
        )
        s.commit()


# ---------- notes ----------
class NoteIn(BaseModel):
    body: str
    artifact_id: str | None = None


@router.get("/cases/{case_id}/notes")
def list_notes(case_id: str, s: SessionDep, artifact_id: str | None = None) -> list[Note]:
    stmt = select(Note).where(Note.case_id == case_id)
    if artifact_id:
        stmt = stmt.where(Note.artifact_id == artifact_id)
    return list(s.exec(stmt.order_by(col(Note.created_at))))


@router.post("/cases/{case_id}/notes", status_code=201)
def create_note(case_id: str, body: NoteIn, s: SessionDep, actor: ActorDep) -> Note:
    if not body.body.strip():
        raise HTTPException(422, "empty note")
    if body.artifact_id:
        a = s.get(Artifact, body.artifact_id)
        if a is None or a.case_id != case_id:
            raise HTTPException(404, "artifact not in case")
    n = Note(case_id=case_id, artifact_id=body.artifact_id, author=actor, body=body.body.strip())
    s.add(n)
    audit.record(
        s,
        actor,
        "note.create",
        case_id=case_id,
        object_type="note",
        object_id=n.id,
        details={"artifact_id": body.artifact_id, "length": len(n.body)},
        commit=False,
    )
    s.commit()
    s.refresh(n)
    return n


# ---------- reports ----------
@router.get("/cases/{case_id}/report.{fmt}")
def export_report(case_id: str, fmt: str, s: SessionDep, actor: ActorDep) -> Response:
    from tracelume import report

    if fmt not in ("html", "pdf"):
        raise HTTPException(404, "format must be html or pdf")
    case = s.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    data, digest = report.export(s, case, actor, fmt)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in case.name)[:60]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return Response(
        data,
        media_type="application/pdf" if fmt == "pdf" else "text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="tracelume-{safe}-{stamp}.{fmt}"',
            "X-Report-SHA256": digest,
        },
    )
