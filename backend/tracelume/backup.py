"""Full backups (database + evidence + results) and restore.

A backup is one .tar.gz in the backups directory containing:
  db/<table>.jsonl   every table, dialect-neutral (restores into SQLite or PostgreSQL)
  evidence/          original evidence files (read-only copies)
  workspace/         tool output, extracted databases, thumbnails
  manifest.json      version, schema revision, counts, created_at
A sidecar <name>.sha256 holds the archive checksum.

Restore (CLI only, into an empty installation):  python -m tracelume.backup restore <file>
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, SQLModel, select

from tracelume import __version__, audit
from tracelume.config import get_settings
from tracelume.db import get_engine

_lock = threading.Lock()
STATUS: dict[str, Any] = {"running": False, "last": None, "error": None}


def backups_dir() -> Path:
    d = get_settings().backups_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_backups() -> list[dict[str, Any]]:
    out = []
    for p in sorted(backups_dir().glob("tracelume-backup-*.tar.gz"), reverse=True):
        side = p.with_name(p.name + ".sha256")
        out.append(
            {
                "name": p.name,
                "size": p.stat().st_size,
                "created": datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat(),
                "sha256": side.read_text().split()[0] if side.exists() else None,
            }
        )
    return out


def _add_bytes(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = int(datetime.now(UTC).timestamp())
    tar.addfile(info, io.BytesIO(data))


def create_backup(actor: str) -> dict[str, Any]:
    from tracelume import models  # noqa: F401

    s_cfg = get_settings()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backups_dir() / f"tracelume-backup-{stamp}.tar.gz"
    tmp = target.with_suffix(".partial")
    counts: dict[str, int] = {}
    with get_engine().connect() as conn, tarfile.open(tmp, "w:gz") as tar:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        for table in SQLModel.metadata.sorted_tables:
            rows = conn.execute(table.select()).mappings().all()
            counts[table.name] = len(rows)
            data = "".join(
                json.dumps(dict(r), default=str, ensure_ascii=False) + "\n" for r in rows
            )
            _add_bytes(tar, f"db/{table.name}.jsonl", data.encode())
        for name, path in (("evidence", s_cfg.evidence_dir), ("workspace", s_cfg.workspace_dir)):
            if path.exists():
                tar.add(path, arcname=name)
        manifest = {
            "tracelume_version": __version__,
            "schema_revision": rev,
            "created_at": datetime.now(UTC).isoformat(),
            "created_by": actor,
            "row_counts": counts,
        }
        _add_bytes(tar, "manifest.json", json.dumps(manifest, indent=1).encode())
    h = hashlib.sha256()
    with tmp.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    tmp.rename(target)
    target.with_name(target.name + ".sha256").write_text(f"{h.hexdigest()}  {target.name}\n")
    with Session(get_engine()) as s:
        audit.record(
            s,
            actor,
            "backup.create",
            object_type="backup",
            object_id=target.name,
            hash_after=h.hexdigest(),
            details={"rows": counts},
        )
    return {"name": target.name, "sha256": h.hexdigest(), "rows": counts}


def start_backup(actor: str) -> bool:
    """Run in a background thread; returns False if one is already running."""
    if not _lock.acquire(blocking=False):
        return False
    STATUS.update(running=True, error=None)

    def work() -> None:
        try:
            STATUS["last"] = create_backup(actor)
        except Exception as e:  # noqa: BLE001
            STATUS["error"] = str(e)
        finally:
            STATUS["running"] = False
            _lock.release()

    threading.Thread(target=work, daemon=True).start()
    return True


def restore(archive: Path) -> None:
    from tracelume import models
    from tracelume.db import init_db

    side = archive.with_name(archive.name + ".sha256")
    if side.exists():
        h = hashlib.sha256(archive.read_bytes()).hexdigest()
        if h != side.read_text().split()[0]:
            raise SystemExit("checksum mismatch — backup is damaged")
    init_db()
    with Session(get_engine()) as s:
        if s.exec(select(models.Case)).first() is not None:
            raise SystemExit("this installation already has cases; restore needs an empty one")
    cfg = get_settings()
    with tarfile.open(archive) as tar:
        manifest = json.loads(tar.extractfile("manifest.json").read())  # type: ignore[union-attr]
        with get_engine().begin() as conn:
            for table in SQLModel.metadata.sorted_tables:
                f = tar.extractfile(f"db/{table.name}.jsonl")
                if f is None:
                    continue
                rows = [json.loads(line) for line in f.read().decode().splitlines() if line]
                for r in rows:
                    for col in table.columns:
                        if r.get(col.name) is not None and col.type.python_type is datetime:
                            r[col.name] = datetime.fromisoformat(r[col.name])
                if rows:
                    conn.execute(table.insert(), rows)
        for m in tar.getmembers():
            for prefix, dest in (
                ("evidence/", cfg.evidence_dir),
                ("workspace/", cfg.workspace_dir),
            ):
                if m.name.startswith(prefix):
                    m.name = m.name[len(prefix) :]
                    tar.extract(m, dest, filter="data")
    print(f"restored backup from {manifest['created_at']} ({manifest['row_counts']})")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "restore":
        restore(Path(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == "create":
        print(create_backup("cli"))
    else:
        raise SystemExit("usage: python -m tracelume.backup create | restore <archive>")
