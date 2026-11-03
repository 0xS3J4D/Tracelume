"""Tracelume SQLite extractor and deleted-record carver (runs inside its own container).

For every SQLite database in the evidence (folder, .zip, .tar, .tar.gz or a single file):
  1. copy it (+ -wal / -journal) to OUTPUT/databases/ and record SHA-256
  2. read live rows read-only (immutable)
  3. recover records that are not live:
       wal        records in WAL frames that are absent from the live database
       freelist   records carved from freelist (unused) pages
       freeblock  records carved from free space inside b-tree leaf pages
Writes OUTPUT/index.json and OUTPUT/recovered.jsonl.

Usage: sqlite_carve.py <evidence> <output>
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import struct
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

MAGIC = b"SQLite format 3\x00"
MAX_DBS = 5000
MAX_DB_SIZE = 2 * 1024**3


# ---------------------------------------------------------------- record decoding
def varint(buf: bytes, pos: int) -> tuple[int, int]:
    """SQLite big-endian varint. Returns (value, new_pos). Raises IndexError past end."""
    v = 0
    for i in range(8):
        b = buf[pos + i]
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, pos + i + 1
    return (v << 8) | buf[pos + 8], pos + 9


def serial_size(t: int) -> int:
    if t in (0, 8, 9, 12, 13):
        return 0 if t < 12 else (t - 12) // 2
    if 1 <= t <= 4:
        return t
    if t == 5:
        return 6
    if t in (6, 7):
        return 8
    if t >= 12:
        return (t - 12) // 2 if t % 2 == 0 else (t - 13) // 2
    raise ValueError(t)  # 10, 11 reserved


def decode_value(t: int, raw: bytes) -> Any:
    if t == 0:
        return None
    if 1 <= t <= 6:
        return int.from_bytes(raw, "big", signed=True)
    if t == 7:
        return struct.unpack(">d", raw)[0]
    if t == 8:
        return 0
    if t == 9:
        return 1
    if t >= 13 and t % 2 == 1:
        return raw.decode("utf-8")  # strict: invalid text => not a record
    return {"blob_hex": raw[:64].hex(), "blob_len": len(raw)}


def parse_record(buf: bytes, pos: int, end: int) -> tuple[list[Any], int] | None:
    """Parse a record (header + body) starting at pos. Returns (values, end_pos) or None."""
    try:
        hlen, p = varint(buf, pos)
        if hlen < 2 or hlen > 512 or pos + hlen > end:
            return None
        types: list[int] = []
        while p < pos + hlen:
            t, p = varint(buf, p)
            if t in (10, 11) or t > 2_000_000:
                return None
            types.append(t)
        if p != pos + hlen or not types:
            return None
        body = pos + hlen
        values: list[Any] = []
        for t in types:
            n = serial_size(t)
            if body + n > end:
                return None
            values.append(decode_value(t, buf[body : body + n]))
            body += n
        return values, body
    except (IndexError, ValueError, UnicodeDecodeError, struct.error):
        return None


def plausible(values: list[Any]) -> bool:
    """Reject random byte runs that happen to parse."""
    if len(values) < 2:
        return False
    texts = [v for v in values if isinstance(v, str)]
    if not texts:
        return False
    for s in texts:
        if s and sum(ch.isprintable() or ch in "\n\r\t" for ch in s) / len(s) < 0.9:
            return False
    return any(len(s) >= 2 for s in texts)


# ---------------------------------------------------------------- page walking
class Db:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        ps = struct.unpack(">H", self.data[16:18])[0]
        self.page_size = 65536 if ps == 1 else ps
        self.reserved = self.data[20]
        self.usable = self.page_size - self.reserved
        self.n_pages = len(self.data) // self.page_size

    def page(self, n: int) -> bytes:  # 1-based
        return self.data[(n - 1) * self.page_size : n * self.page_size]

    def freelist_pages(self) -> list[int]:
        trunk = struct.unpack(">I", self.data[32:36])[0]
        pages, seen = [], set()
        while trunk and trunk <= self.n_pages and trunk not in seen:
            seen.add(trunk)
            pages.append(trunk)
            pg = self.page(trunk)
            nxt, count = struct.unpack(">II", pg[:8])
            count = min(count, (self.usable - 8) // 4)
            for i in range(count):
                leaf = struct.unpack(">I", pg[8 + 4 * i : 12 + 4 * i])[0]
                if 0 < leaf <= self.n_pages:
                    pages.append(leaf)
            trunk = nxt
        return pages


def leaf_cells(page: bytes, hdr_off: int) -> Iterator[list[Any]]:
    """Live cells of a table b-tree leaf page (type 0x0D)."""
    if page[hdr_off] != 0x0D:
        return
    n = struct.unpack(">H", page[hdr_off + 3 : hdr_off + 5])[0]
    for i in range(min(n, 2000)):
        ptr = struct.unpack(">H", page[hdr_off + 8 + 2 * i : hdr_off + 10 + 2 * i])[0]
        try:
            _, p = varint(page, ptr)  # payload length
            _, p = varint(page, p)  # rowid
        except IndexError:
            continue
        rec = parse_record(page, p, len(page))
        if rec:
            yield rec[0]


def carve(region: bytes, start: int, end: int) -> Iterator[tuple[int, list[Any]]]:
    """Scan [start, end) for record headers."""
    i = start
    while i < end - 2:
        rec = parse_record(region, i, end)
        if rec and plausible(rec[0]):
            yield i, rec[0]
            i = max(rec[1], i + 1)
        else:
            i += 1


def parse_headless(
    buf: bytes, pos: int, end: int, n_types: int, prefix: list[int]
) -> tuple[list[Any], int] | None:
    """Parse a record whose header-length byte (and maybe first serial types) were overwritten.

    When SQLite frees a cell it writes a 4-byte freeblock header over its start: the payload
    length, rowid, header length and often the first serial type are lost. Given the table's
    column count we read the surviving serial types and assume the lost ones (`prefix`,
    typically NULL for an INTEGER PRIMARY KEY alias).
    """
    try:
        p = pos
        types = list(prefix)
        for _ in range(n_types):
            t, p = varint(buf, p)
            if t in (10, 11) or t > 2_000_000:
                return None
            types.append(t)
        body = p
        values: list[Any] = []
        for t in types:
            n = serial_size(t)
            if body + n > end:
                return None
            values.append(decode_value(t, buf[body : body + n]))
            body += n
        return values, body
    except (IndexError, ValueError, UnicodeDecodeError, struct.error):
        return None


def carve_freeblock(
    page: bytes, start: int, end: int, widths: set[int]
) -> Iterator[tuple[int, list[Any]]]:
    """Recover the cell at the start of a freeblock, then scan the rest normally."""
    best: tuple[list[Any], int] | None = None
    for n in sorted(widths, reverse=True):
        for prefix_len in (0, 1):
            rec = parse_headless(page, start + 4, end, n - prefix_len, [0] * prefix_len)
            if rec and plausible(rec[0]) and (best is None or rec[1] > best[1]):
                best = rec
    if best:
        yield start, best[0]
        start = best[1]
    yield from carve(page, start, end)


def freeblocks(page: bytes, hdr_off: int) -> Iterator[tuple[int, int, bool]]:
    """(start, end, is_freeblock) for the unallocated gap and every freeblock of a leaf page."""
    if page[hdr_off] != 0x0D:
        return
    first = struct.unpack(">H", page[hdr_off + 1 : hdr_off + 3])[0]
    n_cells = struct.unpack(">H", page[hdr_off + 3 : hdr_off + 5])[0]
    content = struct.unpack(">H", page[hdr_off + 5 : hdr_off + 7])[0] or 65536
    gap_start = hdr_off + 8 + 2 * n_cells
    if content > gap_start:
        yield gap_start, min(content, len(page)), False
    seen, fb = set(), first
    while fb and fb not in seen and fb + 4 <= len(page):
        seen.add(fb)
        nxt, size = struct.unpack(">HH", page[fb : fb + 4])
        yield fb, min(fb + size, len(page)), True
        fb = nxt


# ---------------------------------------------------------------- per database
def live_rows(path: Path) -> tuple[dict[str, dict[str, Any]], set[tuple[str, ...]]]:
    uri = f"file:{path}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    con.execute("PRAGMA trusted_schema=OFF")
    tables: dict[str, dict[str, Any]] = {}
    keys: set[tuple[str, ...]] = set()
    try:
        for (name,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall():
            q = name.replace('"', '""')
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{q}")')]
            # identifiers come from the database's own schema and are quoted
            count = con.execute(f'SELECT count(*) FROM "{q}"').fetchone()[0]  # noqa: S608
            tables[name] = {"columns": cols, "rows": count}
            for row in con.execute(f'SELECT * FROM "{q}" LIMIT 200000'):  # noqa: S608
                keys.add(_key(list(row)))
    finally:
        con.close()
    return tables, keys


def _key(values: list[Any]) -> tuple[str, ...]:
    return tuple(json.dumps(v, default=str) for v in values if not isinstance(v, bytes))


def guess_table(values: list[Any], tables: dict[str, dict[str, Any]]) -> str | None:
    matches = [n for n, t in tables.items() if len(t["columns"]) == len(values)]
    return matches[0] if len(matches) == 1 else None


def analyse(db_path: Path, rel: str, out: Any) -> dict[str, Any]:
    info: dict[str, Any] = {"path": rel, "size": db_path.stat().st_size}
    info["sha256"] = hashlib.sha256(db_path.read_bytes()).hexdigest()
    try:
        tables, live = live_rows(db_path)
    except sqlite3.DatabaseError as e:
        info["error"] = f"unreadable: {e}"
        return info
    info["tables"] = tables
    db = Db(db_path)
    seen: set[tuple[str, ...]] = set()
    counts = {"wal": 0, "freelist": 0, "freeblock": 0}
    widths = {len(t["columns"]) for t in tables.values() if t["columns"]}

    def emit(source: str, page: int, offset: int, values: list[Any]) -> None:
        k = _key(values)
        if k in live or (source, k) in seen:
            return
        seen.add((source, k))
        counts[source] += 1
        out.write(
            json.dumps(
                {
                    "db": rel,
                    "source": source,
                    "page": page,
                    "offset": offset,
                    "table_guess": guess_table(values, tables),
                    "values": values,
                },
                default=str,
            )
            + "\n"
        )

    for pno in db.freelist_pages():
        for off, vals in carve(db.page(pno), 0, db.usable):
            emit("freelist", pno, off, vals)
    for pno in range(1, db.n_pages + 1):
        pg = db.page(pno)
        hdr = 100 if pno == 1 else 0
        for s, e, is_fb in freeblocks(pg, hdr):
            found = carve_freeblock(pg, s, e, widths) if is_fb else carve(pg, s, e)
            for off, vals in found:
                emit("freeblock", pno, off, vals)

    wal = db_path.with_name(db_path.name + "-wal")
    if wal.exists() and wal.stat().st_size > 32:
        w = wal.read_bytes()
        psz = struct.unpack(">I", w[8:12])[0]
        if psz in (512, 1024, 2048, 4096, 8192, 16384, 32768, 65536):
            pos, frame = 32, 0
            while pos + 24 + psz <= len(w):
                pno = struct.unpack(">I", w[pos : pos + 4])[0]
                page = w[pos + 24 : pos + 24 + psz]
                hdr = 100 if pno == 1 else 0
                for vals in leaf_cells(page, hdr):
                    if plausible(vals):
                        emit("wal", pno, frame, vals)
                pos += 24 + psz
                frame += 1
            info["wal_frames"] = frame
    info["recovered"] = counts
    return info


# ---------------------------------------------------------------- evidence walking
def is_sqlite(p: Path) -> bool:
    try:
        with p.open("rb") as f:
            return f.read(16) == MAGIC
    except OSError:
        return False


def stage(evidence: Path, tmp: Path) -> Path:
    name = evidence.name.lower()
    if evidence.is_dir():
        return evidence
    if name.endswith(".zip"):
        with zipfile.ZipFile(evidence) as z:
            for m in z.infolist():
                if m.is_dir() or m.file_size > MAX_DB_SIZE:
                    continue
                with z.open(m) as f:
                    head = f.read(16)
                base = m.filename.rsplit("/", 1)[-1]
                if head == MAGIC or base.endswith(("-wal", "-journal")):
                    z.extract(m, tmp)
        return tmp
    if name.endswith((".tar", ".tar.gz", ".tgz")):
        with tarfile.open(evidence) as t:
            t.extractall(tmp, filter="data")
        return tmp
    return evidence.parent if is_sqlite(evidence) else tmp


def main() -> None:
    evidence, out = Path(sys.argv[1]), Path(sys.argv[2])
    dbs_dir = out / "databases"
    dbs_dir.mkdir(parents=True, exist_ok=True)
    index: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(dir=out) as tmpd:
        root = stage(evidence, Path(tmpd))
        candidates = (
            [evidence]
            if evidence.is_file() and is_sqlite(evidence)
            else [
                p
                for p in sorted(root.rglob("*"))
                if p.is_file() and not p.is_symlink() and is_sqlite(p)
            ]
        )
        print(f"found {len(candidates)} SQLite databases", flush=True)
        with (out / "recovered.jsonl").open("w", encoding="utf-8") as rec_out:
            for i, src in enumerate(candidates[:MAX_DBS]):
                rel = str(src.relative_to(root)) if src.is_relative_to(root) else src.name
                dest = dbs_dir / f"{i:05d}_{src.name}"
                shutil.copyfile(src, dest)
                for suffix in ("-wal", "-journal"):
                    side = src.with_name(src.name + suffix)
                    if side.exists():
                        shutil.copyfile(side, dest.with_name(dest.name + suffix))
                info = analyse(dest, rel, rec_out)
                info["file"] = dest.name
                index.append(info)
                rc = info.get("recovered", {})
                print(f"  {rel}: {len(info.get('tables', {}))} tables, recovered {rc}", flush=True)
    (out / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    for p in dbs_dir.iterdir():
        os.chmod(p, 0o444)


if __name__ == "__main__":
    main()
