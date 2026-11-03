"""Case export bundle: everything needed to review or archive a case outside Tracelume."""

import csv
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from tracelume import __version__, audit, report
from tracelume.models import Artifact, ArtifactTag, AuditLog, Case, Evidence, Job, Note, Tag


def _dump(rows: list[Any]) -> bytes:
    return json.dumps(
        [r.model_dump(mode="json") for r in rows], indent=1, ensure_ascii=False
    ).encode()


def build_bundle(s: Session, case: Case, actor: str, with_pdf: bool = True) -> bytes:
    cid = case.id
    files: dict[str, bytes] = {}
    html = report.render_html(s, case, actor)
    files["report.html"] = html.encode()
    if with_pdf:
        files["report.pdf"] = report.render_pdf(html)
    ev = list(s.exec(select(Evidence).where(Evidence.case_id == cid)))
    files["evidence.json"] = _dump(ev)
    files["jobs.json"] = _dump(list(s.exec(select(Job).where(Job.case_id == cid))))
    files["notes.json"] = _dump(list(s.exec(select(Note).where(Note.case_id == cid))))
    tags = list(s.exec(select(Tag).where(Tag.case_id == cid)))
    files["tags.json"] = _dump(tags)
    links = s.exec(
        select(ArtifactTag).join(Tag, col(Tag.id) == ArtifactTag.tag_id).where(Tag.case_id == cid)
    ).all()
    files["artifact_tags.json"] = _dump(list(links))
    files["audit_log.json"] = _dump(
        list(s.exec(select(AuditLog).where(AuditLog.case_id == cid).order_by(col(AuditLog.id))))
    )

    jl, cs = io.StringIO(), io.StringIO()
    w = csv.writer(cs)
    w.writerow(
        [
            "id",
            "timestamp_utc",
            "timestamp_kind",
            "type",
            "title",
            "source_plugin",
            "source_path",
            "evidence_id",
            "data_json",
        ]
    )
    for a in s.exec(
        select(Artifact)
        .where(Artifact.case_id == cid)
        .order_by(col(Artifact.timestamp).asc().nulls_last())
    ):
        jl.write(json.dumps(a.model_dump(mode="json"), ensure_ascii=False) + "\n")
        w.writerow(
            [
                a.id,
                a.timestamp.isoformat() if a.timestamp else "",
                a.timestamp_kind or "",
                a.type,
                a.title,
                a.source_plugin,
                a.source_path or "",
                a.evidence_id,
                json.dumps(a.data, ensure_ascii=False),
            ]
        )
    files["artifacts.jsonl"] = jl.getvalue().encode()
    files["artifacts.csv"] = cs.getvalue().encode("utf-8-sig")
    files["manifest.json"] = json.dumps(
        {
            "case": case.model_dump(mode="json"),
            "exported_at": datetime.now(UTC).isoformat(),
            "exported_by": actor,
            "tracelume_version": __version__,
            "evidence_hashes": {
                e.original_filename: {"sha256": e.sha256, "md5": e.md5} for e in ev
            },
            "note": "Evidence files are not included; verify them with these hashes.",
        },
        indent=1,
    ).encode()
    sums = "".join(f"{hashlib.sha256(b).hexdigest()}  {n}\n" for n, b in sorted(files.items()))
    files["SHA256SUMS"] = sums.encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    data = buf.getvalue()
    audit.record(
        s,
        actor,
        "case.export",
        case_id=cid,
        object_type="case",
        object_id=cid,
        hash_after=hashlib.sha256(data).hexdigest(),
        details={"files": sorted(files)},
    )
    return data
