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
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(db, "data/data/com.android.providers.telephony/databases/mmssms.db")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("import/synthetic-android.zip")
    print(build(target))
