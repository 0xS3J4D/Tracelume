"""Shared helpers for plugin parsers."""

from datetime import UTC, datetime
from typing import Any


def iso_utc(v: Any) -> datetime | None:
    """Parse an ISO-8601-ish string. Naive values are treated as UTC: only call this for
    sources documented to emit UTC. Handles 'Z', 7-digit .NET fractions, and spaces."""
    if not isinstance(v, str) or not v.strip() or v.startswith(("0000", "1601-01-01")):
        return None
    s = v.strip().replace(" ", "T", 1).replace("Z", "+00:00")
    if "." in s:  # trim fractions longer than microseconds (.NET writes 7 digits)
        head, _, tail = s.partition(".")
        digits = "".join(c for c in tail if c.isdigit())
        rest = tail[len(digits) :]
        s = f"{head}.{digits[:6]}{rest}"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
