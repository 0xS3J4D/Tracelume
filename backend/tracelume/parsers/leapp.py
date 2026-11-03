"""Shared parser for xLEAPP (ALEAPP / iLEAPP) TSV exports.

Both tools write one TSV per artifact module to `<report>/_TSV Exports/<name>.tsv` and report
timestamps in UTC unless a timezone offset is configured (Tracelume never sets one).
"""

from __future__ import annotations

import ast
import csv
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from tracelume.plugins.base import ArtifactIn

csv.field_size_limit(1 << 28)

# (pattern on TSV file name, artifact type, title template keys)
TYPE_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(sms|mms|messages?|chats?|whatsapp|telegram|signal|imo|kik)\b", re.I),
        "message",
    ),
    (re.compile(r"call ?log|calls?\b", re.I), "call"),
    (re.compile(r"contacts?", re.I), "contact"),
    (re.compile(r"location|gps|geo|places|cell tower|wifi.*location", re.I), "location"),
    (
        re.compile(
            r"(browser|chrome|firefox|web).*(history|visits|searches|downloads)|"
            r"(history|visits).*(browser|chrome)",
            re.I,
        ),
        "web_history",
    ),
    (
        re.compile(
            r"usage ?stats|app ?usage|recent ?activity|screen ?time|knowledgec|biome|"
            r"powerlog|app ?intents?",
            re.I,
        ),
        "app_usage",
    ),
    (re.compile(r"accounts?", re.I), "account"),
    (re.compile(r"photos?|images?|media|gallery|camera|thumbnails?", re.I), "media"),
]

TIME_HEADER = re.compile(r"time|date|created|modified|accessed|last ?seen|visit", re.I)
TITLE_KEYS = (
    "body",
    "message",
    "text",
    "title",
    "url",
    "name",
    "display name",
    "address",
    "phone number",
    "number",
    "package name",
    "app name",
    "file name",
)
DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def classify(tsv_name: str) -> str:
    for pattern, kind in TYPE_RULES:
        if pattern.search(tsv_name):
            return kind
    return "event"


def clean_header(h: str) -> str:
    """Newer ALEAPP versions may emit typed headers like "('Timestamp', 'datetime')"."""
    h = h.strip()
    if h.startswith("(") and h.endswith(")"):
        try:
            val = ast.literal_eval(h)
            if isinstance(val, tuple) and val:
                return str(val[0])
        except (ValueError, SyntaxError):
            pass
    return h


def parse_ts(value: str) -> datetime | None:
    """ALEAPP reports in UTC unless a timezone offset is configured (we never set one).
    Naive values are therefore treated as UTC; explicit offsets are honoured."""
    v = value.strip()
    if not v or v.lower() in {"none", "null", "n/a", "0"}:
        return None
    v = v.removesuffix(" UTC").replace("Z", "+00:00")
    dt: datetime | None = None
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        for fmt in DATE_FORMATS:
            try:
                dt = datetime.strptime(v, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.year < 1971:
        return None  # epoch-zero placeholders
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def make_title(kind: str, module: str, row: dict[str, str]) -> str:
    lower = {k.lower(): v for k, v in row.items() if v}
    for key in TITLE_KEYS:
        if lower.get(key):
            return f"{module}: {lower[key]}"[:500]
    first = next((v for v in row.values() if v), "")
    return f"{module}: {first}"[:500] if first else module


def iter_tsv(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header: list[str] | None = None
        raw_header: list[str] | None = None
        for row in reader:
            if header is None:
                raw_header, header = row, [clean_header(h) for h in row]
                continue
            if row == raw_header:  # ALEAPP appends: repeated header blocks
                continue
            yield {header[i] if i < len(header) else f"col{i}": v for i, v in enumerate(row)}


def row_to_artifact(module: str, kind: str, row: dict[str, str]) -> ArtifactIn:
    ts, ts_kind = None, None
    for key, val in row.items():
        if TIME_HEADER.search(key) and val:
            ts = parse_ts(val)
            if ts:
                ts_kind = key
                break
    source = row.get("Source File") or row.get("Source") or None
    return ArtifactIn(
        type=kind,
        title=make_title(kind, module, row),
        timestamp=ts,
        timestamp_kind=ts_kind,
        source_path=source,
        data={"module": module, **row},
    )


def parse_report(output_dir: Path) -> Iterator[ArtifactIn]:
    for tsv in sorted(output_dir.rglob("_TSV Exports/*.tsv")):
        module = tsv.stem
        if module.startswith("_"):  # tool bookkeeping files
            continue
        kind = classify(module)
        for row in iter_tsv(tsv):
            if any(row.values()):
                yield row_to_artifact(module, kind, row)
