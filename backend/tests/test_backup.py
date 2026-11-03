import tarfile
import time

from fastapi.testclient import TestClient


def test_backup_and_restore_roundtrip(
    client: TestClient, populated: str, tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    assert client.post("/api/backups").status_code == 202
    for _ in range(100):
        st = client.get("/api/backups").json()
        if not st["status"]["running"] and st["backups"]:
            break
        time.sleep(0.05)
    assert st["status"]["error"] is None
    b = st["backups"][0]
    assert b["sha256"] and b["size"] > 0
    archive = tmp_path / "data_backups"  # locate file
    from tracelume import backup

    path = backup.backups_dir() / b["name"]
    with tarfile.open(path) as t:
        names = t.getnames()
    assert "manifest.json" in names and "db/artifact.jsonl" in names
    assert any(n.startswith("evidence/") for n in names)

    # restore into a fresh, empty installation
    from tracelume.config import get_settings
    from tracelume.db import get_engine

    fresh = tmp_path / "fresh"
    monkeypatch.setenv("TRACELUME_DATABASE_URL", f"sqlite:///{fresh}/t.db")
    monkeypatch.setenv("TRACELUME_EVIDENCE_DIR", str(fresh / "evidence"))
    monkeypatch.setenv("TRACELUME_WORKSPACE_DIR", str(fresh / "work"))
    get_settings.cache_clear()
    get_engine.cache_clear()
    backup.restore(path)
    from sqlmodel import Session, select

    from tracelume.models import Artifact, AuditLog

    with Session(get_engine()) as s:
        assert len(s.exec(select(Artifact)).all()) == 6
        assert s.exec(select(AuditLog)).first() is not None
    from tracelume import audit

    with Session(get_engine()) as s:
        assert audit.verify_chain(s)[0]  # chain survives the round trip
    assert any((fresh / "evidence").rglob("dump.zip"))
    del archive
