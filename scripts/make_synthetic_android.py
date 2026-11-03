"""Build a tiny SYNTHETIC Android file-system dump for demos and integration tests.

Produces data/import/synthetic-android.zip containing an mmssms.db with fake messages.
Contains no real personal data. Usage: python scripts/make_synthetic_android.py [out.zip]
"""

import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

MESSAGES = [  # (address, epoch ms, type 1=received 2=sent, body)
    ("+15550100", 1714554902000, 1, "Synthetic message — meet at the library at 10?"),
    ("+15550100", 1714555000000, 2, "Sounds good. Bringing the notes."),
    ("+15550142", 1714651200000, 1, "Test data only: package delivered."),
]


CHAT = [  # (id, sender, body, epoch ms); ids 4-6 are deleted afterwards
    (1, "alex", "Are we still on for Friday?", 1714555200000),
    (2, "me", "Yes — 19:00 at the usual place.", 1714555260000),
    (3, "alex", "Bring the documents.", 1714555320000),
    (4, "me", "Deleted: I moved the files to the blue drive.", 1714555380000),
    (5, "alex", "Deleted: Don't mention it on the phone.", 1714555440000),
    (6, "me", "Deleted: Understood.", 1714555500000),
    (7, "alex", "See you then.", 1714555560000),
]
PHOTOS = [  # (name, lat, lon, "YYYY:MM:DD HH:MM:SS", offset)
    ("IMG_20240501_101500.jpg", 59.9139, 10.7522, "2024:05:01 10:15:00", "+02:00"),
    ("IMG_20240501_134210.jpg", 59.9075, 10.7531, "2024:05:01 13:42:10", "+02:00"),
    ("IMG_20240502_081200.jpg", 60.3913, 5.3221, "2024:05:02 08:12:00", None),
]


def _chat_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute("PRAGMA secure_delete=OFF")
    con.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, sender TEXT, body TEXT, ts INTEGER)"
    )
    con.executemany("INSERT INTO messages VALUES (?,?,?,?)", CHAT)
    con.commit()
    con.execute("DELETE FROM messages WHERE id BETWEEN 4 AND 6")
    con.commit()
    con.close()


def _photo(path: Path, lat: float, lon: float, when: str, offset: str | None) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False

    def dms(v: float) -> tuple[float, float, float]:
        d = int(v)
        m = int((v - d) * 60)
        return (float(d), float(m), round(((v - d) * 60 - m) * 60, 2))

    img = Image.new("RGB", (960, 720), (40, 90 + int(lat) % 100, 140))
    exif = Image.Exif()
    exif[0x010F], exif[0x0110] = "Synthetic", "Demo Camera"
    ifd = exif.get_ifd(0x8769)
    ifd[0x9003] = when
    if offset:
        ifd[0x9011] = offset
    gps = exif.get_ifd(0x8825)
    gps.update({1: "N", 2: dms(lat), 3: "E", 4: dms(lon)})
    img.save(path, exif=exif)
    return True


def build(out: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "mmssms.db"
        con = sqlite3.connect(db)
        con.executescript(
            """
            CREATE TABLE sms (_id INTEGER PRIMARY KEY, thread_id INTEGER, address TEXT,
              person INTEGER, date INTEGER, date_sent INTEGER, read INTEGER, type INTEGER,
              body TEXT, service_center TEXT, error_code INTEGER);
            CREATE TABLE pdu (_id INTEGER PRIMARY KEY, thread_id INTEGER, date INTEGER,
              date_sent INTEGER, read INTEGER, msg_box INTEGER);
            CREATE TABLE part (_id INTEGER PRIMARY KEY, mid INTEGER, seq INTEGER, ct TEXT,
              cl TEXT, _data TEXT, text TEXT);
            CREATE TABLE addr (_id INTEGER PRIMARY KEY, msg_id INTEGER, address TEXT,
              type INTEGER);
            """
        )
        for i, (addr, ms, typ, body) in enumerate(MESSAGES, 1):
            con.execute(
                "INSERT INTO sms VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (i, 1 if addr.endswith("100") else 2, addr, None, ms, ms, 1, typ, body, None, 0),
            )
        con.commit()
        con.close()
        chat = Path(tmp) / "chat.db"
        _chat_db(chat)
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(db, "data/data/com.android.providers.telephony/databases/mmssms.db")
            z.write(chat, "data/data/com.example.chat/databases/chat.db")
            for name, lat, lon, when, off in PHOTOS:
                ph = Path(tmp) / name
                if _photo(ph, lat, lon, when, off):
                    z.write(ph, f"sdcard/DCIM/Camera/{name}")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("import/synthetic-android.zip")
    print(build(target))
