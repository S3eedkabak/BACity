"""
Normalizes the wide variety of date/time strings real Bratislava sources
use (spec section 20 / 26) into timezone-aware UTC datetimes.

Handles, among others:
    "28 August 2026, 20:00"
    "28/08/2026 20:00"
    "Aug 28 @ 8 PM"
    "Piatok 28. 8. od 20:00"      (Slovak: "Friday 28.8 from 20:00")
    "28. 8. 2026, 20:00"
    ISO 8601 straight through ("2026-08-28T20:00:00+02:00")

Strategy: strip known Slovak day-name / filler words, then try dateutil's
general parser (handles the large majority of English/ISO formats), and
fall back to an explicit "DD. MM.[ YYYY][, ]HH:MM" regex for the Slovak
dot-separated style dateutil doesn't reliably parse (e.g. "28. 8.").
"""
import re
from datetime import datetime
from typing import Optional

import pytz
from dateutil import parser as dateutil_parser

DEFAULT_TZ = pytz.timezone("Europe/Bratislava")

# Matches unambiguous ISO 8601 date(time) strings, e.g. "2026-12-01" or
# "2026-12-01T20:00:00+01:00". These must NOT go through the dayfirst=True
# fuzzy parser below: dateutil's dayfirst flag can incorrectly swap
# month/day on already-unambiguous YYYY-MM-DD strings (verified bug:
# parse("2026-12-01T20:00:00+01:00", dayfirst=True) silently returns
# Jan 12 instead of Dec 1). isoparse() handles this format correctly and
# is what schema.org/JSON-LD startDate values use almost universally.
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?")

SK_DAY_NAMES = [
    "pondelok", "utorok", "streda", "štvrtok", "stvrtok", "piatok",
    "sobota", "nedeľa", "nedela",
]
FILLER_WORDS = ["od", "o ", "at "]

_SK_DATE_RE = re.compile(
    r"""
    (?P<day>\d{1,2})\.\s*
    (?P<month>\d{1,2})\.
    (?:\s*(?P<year>\d{4}))?
    [,\s]*
    (?:(?:od\s*)?(?P<hour>\d{1,2}):(?P<minute>\d{2}))?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _strip_slovak_noise(text: str) -> str:
    cleaned = text.strip()
    for day in SK_DAY_NAMES:
        cleaned = re.sub(rf"\b{day}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("@", " ")
    return cleaned.strip(" ,")


def parse_event_datetime(
    raw: str, *, reference_year: Optional[int] = None, tz=DEFAULT_TZ
) -> Optional[datetime]:
    """Best-effort parse of a single date/time string into a tz-aware datetime.
    Returns None (rather than raising) on unparseable input — callers should
    treat that as a validation failure, not a crash (spec section 12: a
    failed source/page must not take down the pipeline)."""
    if not raw or not raw.strip():
        return None

    cleaned = _strip_slovak_noise(raw)
    reference_year = reference_year or datetime.now(tz).year

    # 0. Unambiguous ISO 8601 -- parse directly, skip the dayfirst-fuzzy
    # path entirely (see _ISO_RE comment above for why this matters).
    if _ISO_RE.match(cleaned.strip()):
        try:
            parsed = dateutil_parser.isoparse(cleaned.strip())
            if parsed.tzinfo is None:
                return tz.localize(parsed)
            return parsed
        except ValueError:
            pass  # fall through to the general-purpose paths below

    # 1. Slovak dot-separated style: "28. 8." / "28. 8. 2026, 20:00"
    m = _SK_DATE_RE.search(cleaned)
    if m and m.group("day") and m.group("month"):
        try:
            day = int(m.group("day"))
            month = int(m.group("month"))
            year = int(m.group("year")) if m.group("year") else reference_year
            hour = int(m.group("hour")) if m.group("hour") else 0
            minute = int(m.group("minute")) if m.group("minute") else 0
            naive = datetime(year, month, day, hour, minute)
            return tz.localize(naive)
        except ValueError:
            pass  # fall through to dateutil

    # 2. Everything else: ISO 8601, "28/08/2026 20:00", "Aug 28 8 PM", etc.
    try:
        parsed = dateutil_parser.parse(cleaned, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError):
        return None

    if parsed.tzinfo is None:
        return tz.localize(parsed)
    return parsed


def parse_price(raw: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """'€10' / '10 EUR' / 'Free' / 'zdarma' / 'voľný vstup' -> (amount, currency)."""
    if raw is None:
        return None, None
    text = raw.strip().lower()
    if not text:
        return None, None
    if any(w in text for w in ["free", "zdarma", "voľný vstup", "volny vstup", "vstup zdarma"]):
        return 0.0, "EUR"

    match = re.search(r"(\d+[.,]?\d*)", text)
    if not match:
        return None, None
    amount = float(match.group(1).replace(",", "."))
    currency = "EUR" if ("€" in raw or "eur" in text) else None
    return amount, currency
