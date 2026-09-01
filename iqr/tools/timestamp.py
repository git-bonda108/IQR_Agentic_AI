"""Parse, timezone-normalize, and order timestamps -> deterministic UTC compare.

Covers the 10032 case: a workbook cell stamped in GMT vs an email Date header
in CDT. Everything is normalized to UTC before any comparison.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dateutil import parser as dtparser
from dateutil import tz as dttz

_TZ_ALIASES = {
    "GMT": dttz.UTC, "UTC": dttz.UTC,
    "CDT": dttz.gettz("America/Chicago"), "CST": dttz.gettz("America/Chicago"),
    "EDT": dttz.gettz("America/New_York"), "EST": dttz.gettz("America/New_York"),
    "PDT": dttz.gettz("America/Los_Angeles"), "PST": dttz.gettz("America/Los_Angeles"),
}


def parse_timestamp(raw: str, assume_tz: str | None = None) -> datetime:
    """Parse a timestamp string; honor an explicit tz token in the string,
    else fall back to assume_tz, else UTC. Returns an aware UTC datetime."""
    if not isinstance(raw, str):
        raw = str(raw)
    cleaned = raw.strip()
    token_tz = None
    for token, zone in _TZ_ALIASES.items():
        if token in cleaned.upper().split() or cleaned.upper().endswith(token):
            token_tz = zone
            cleaned = cleaned.upper().replace(token, "").strip()
            cleaned = raw[: raw.upper().rfind(token)].strip() if token in raw.upper() else cleaned
            break
    dt = dtparser.parse(cleaned, tzinfos={k: v for k, v in _TZ_ALIASES.items()})
    if dt.tzinfo is None:
        zone = token_tz or (_TZ_ALIASES.get((assume_tz or "UTC").upper(), dttz.UTC))
        dt = dt.replace(tzinfo=zone)
    elif token_tz is not None:
        dt = dt.replace(tzinfo=token_tz)
    return dt.astimezone(timezone.utc)


def in_order(earlier: datetime, later: datetime,
             min_gap: timedelta = timedelta(0)) -> bool:
    return (later - earlier) >= min_gap
