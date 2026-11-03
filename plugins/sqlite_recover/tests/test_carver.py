"""The carver is plain Python, so it is tested directly on synthetic databases."""

import json
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

TOOL = Path(__file__).parents[1] / "sqlite_carve.py"


def _make_db(path: Path, wal: bool = False) -> None:
    con = sqlite3.connect(path)
    con.execute("PRAGMA secure_delete=OFF")
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA wal_autocheckpoint=0")
    con.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, sender TEXT, body TEXT, ts INTEGER)"
    )
    rows = [
        (i, f"+1555010{i:03d}", f"message number {i} synthetic", 1714554902000 + i)
        for i in range(1, 400)
    ]
    con.executemany("INSERT INTO messages VALUES (?,?,?,?)", rows)
    con.commit()
    if wal:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute(
            "INSERT INTO messages VALUES (1000, '+15550999', 'only in wal then deleted', 1)"
        )
        con.commit()
        con.execute("DELETE FROM messages WHERE id = 1000")
        con.commit()
        # keep the WAL: copy files while the connection is still open
        return_con = con
        return return_con  # type: ignore[return-value]
    con.execute("DELETE FROM messages WHERE id = 7")  # -> freeblock
    con.execute("DELETE FROM messages WHERE id BETWEEN 100 AND 380")  # -> freelist pages
    con.commit()
    con.close()


def _run(evidence: Path, out: Path) -> tuple[list[dict], list[dict]]:  # type: ignore[type-arg]
    subprocess.run([sys.executable, "-I", str(TOOL), str(evidence), str(out)], check=True)
    index = json.loads((out / "index.json").read_text())
    rec = [json.loads(x) for x in (out / "recovered.jsonl").read_text().splitlines()]
    return index, rec


def test_recovers_deleted_rows_from_free_space(tmp_path: Path) -> None:
    db = tmp_path / "ev" / "chat.db"
    db.parent.mkdir()
    _make_db(db)
    index, rec = _run(db, tmp_path / "out")
    assert index[0]["tables"]["messages"]["rows"] == 399 - 1 - 281
    bodies = {r["values"][2] for r in rec if len(r["values"]) == 4}
    assert "message number 7 synthetic" in bodies
    assert sum(1 for b in bodies if b.startswith("message number 2")) > 10  # freelist range
    live_hit = "message number 5 synthetic"
    assert live_hit not in bodies  # live rows are never reported as recovered
    assert {r["source"] for r in rec} <= {"freelist", "freeblock", "wal"}
    assert any(r["table_guess"] == "messages" for r in rec)
    copied = tmp_path / "out" / "databases" / index[0]["file"]
    assert copied.exists() and not (copied.stat().st_mode & 0o222)


def test_wal_only_records_and_zip_input(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    db = src / "app.db"
    con = _make_db(db, wal=True)
    zpath = tmp_path / "ev" / "dump.zip"
    zpath.parent.mkdir()
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(db, "data/data/com.example/databases/app.db")
        z.write(src / "app.db-wal", "data/data/com.example/databases/app.db-wal")
        z.writestr("data/readme.txt", "not a database")
    con.close()  # type: ignore[attr-defined]
    index, rec = _run(zpath, tmp_path / "out")
    assert index[0]["path"].endswith("com.example/databases/app.db")
    assert index[0]["wal_frames"] >= 1
    wal = [r for r in rec if r["source"] == "wal"]
    assert any(r["values"][2] == "only in wal then deleted" for r in wal)


def test_recovers_each_of_several_adjacent_deleted_rows(tmp_path: Path) -> None:
    """Adjacent freed cells merge into one freeblock but each lost its own first 4 bytes."""
    db = tmp_path / "ev" / "chat.db"
    db.parent.mkdir()
    con = sqlite3.connect(db)
    con.execute("PRAGMA secure_delete=OFF")
    con.execute("CREATE TABLE m (id INTEGER PRIMARY KEY, who TEXT, body TEXT, ts INTEGER)")
    rows = [
        (i, "alex" if i % 2 else "me", f"text {i} " + "x" * i, 1714555200000 + i)
        for i in range(1, 9)
    ]
    con.executemany("INSERT INTO m VALUES (?,?,?,?)", rows)
    con.commit()
    con.execute("DELETE FROM m WHERE id BETWEEN 3 AND 6")
    con.commit()
    con.close()
    _, rec = _run(db, tmp_path / "out")
    got = sorted(tuple(r["values"][1:]) for r in rec)
    assert got == sorted((who, body, ts) for i, who, body, ts in rows if 3 <= i <= 6)
