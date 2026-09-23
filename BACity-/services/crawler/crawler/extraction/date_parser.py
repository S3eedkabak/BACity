"""Date and price normalization for Slovak and English event sources."""
import re
from datetime import datetime
from typing import Optional

import pytz
from dateutil import parser as dateutil_parser

DEFAULT_TZ = pytz.timezone("Europe/Bratislava")

_MONTHS = {
    "január": 1, "januara": 1, "jan": 1,
    "február": 2, "februara": 2, "feb": 2,
    "marec": 3, "marca": 3, "mar": 3,
    "apríl": 4, "aprila": 4, "apr": 4,
    "máj": 5, "maja": 5, "may": 5,
    "jún": 6, "juna": 6, "jun": 6,
    "júl": 7, "jula": 7, "jul": 7,
    "august": 8, "augusta": 8, "aug": 8,
    "september": 9, "septembra": 9, "sep": 9, "sept": 9,
    "október": 10, "oktobra": 10, "oct": 10, "october": 10, "oct": 10,
    "november": 11, "novembra": 11, "nov": 11, "november": 11,
    "december": 12, "decembra": 12, "dec": 12, "december": 12,
}

_DAY_NAMES = (
    "pondelok", "utorok", "streda", "štvrtok", "stvrtok", "piatok",
    "sobota", "nedeľa", "nedela",
)

_MONTH_NAME_RE = "|".join(sorted(map(re.escape, _MONTHS), key=len, reverse=True))
_SK_NAMED_DATE_RE = re.compile(
    rf"(?P<day>\d{{1,2}})\.\s*(?:–|-|až)?\s*"
    rf"(?:(?P<end_day>\d{{1,2}})\.\s*)?"
    rf"(?P<month>{_MONTH_NAME_RE})"
    rf"(?:\s+(?P<year>\d{{4}}))?"
    rf"(?:[,\s]+(?P<hour>\d{{1,2}})(?:[:.](?P<minute>\d{{2}})))?",
    re.IGNORECASE,
)
_SK_DOT_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\.\s*(?P<month>\d{1,2})\.\s*"
    r"(?:(?P<year>\d{4}))?"
    r"(?:[,\s]+(?P<hour>\d{1,2})[:.](?P<minute>\d{2}))?"
)
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?.*)?$")


def _strip_noise(text: str) -> str:
    cleaned = text.replace("\xa0", " ").replace("@", " ")
    for day in _DAY_NAMES:
        cleaned = re.sub(rf"\b{re.escape(day)}\b", " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" ,")


def _localize(dt: datetime, tz):
    return dt if dt.tzinfo else tz.localize(dt)


def parse_event_datetime(
    raw: str, *, reference_year: Optional[int] = None, tz=DEFAULT_TZ
) -> Optional[datetime]:
    if not raw or not raw.strip():
        return None

    cleaned = _strip_noise(raw)
    reference_year = reference_year or datetime.now(tz).year

    if _ISO_RE.match(cleaned):
        try:
            parsed = dateutil_parser.isoparse(cleaned)
            return _localize(parsed, tz)
        except ValueError:
            pass

    match = _SK_NAMED_DATE_RE.search(cleaned)
    if match:
        try:
            day = int(match.group("day"))
            month = _MONTHS[match.group("month").lower()]
            year = int(match.group("year") or reference_year)
            hour = int(match.group("hour") or 0)
            minute = int(match.group("minute") or 0)
            return tz.localize(datetime(year, month, day, hour, minute))
        except (KeyError, ValueError):
            pass

    match = _SK_DOT_DATE_RE.search(cleaned)
    if match:
        try:
            return tz.localize(
                datetime(
                    int(match.group("year") or reference_year),
                    int(match.group("month")),
                    int(match.group("day")),
                    int(match.group("hour") or 0),
                    int(match.group("minute") or 0),
                )
            )
        except ValueError:
            pass

    try:
        parsed = dateutil_parser.parse(cleaned, dayfirst=True, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None

    return _localize(parsed, tz)


def parse_price(raw: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    if raw is None:
        return None, None
    text = raw.strip().lower()
    if not text:
        return None, None

    if any(
        word in text
        for word in ("free", "zdarma", "voľný vstup", "volny vstup", "vstup zdarma")
    ):
        return 0.0, "EUR"

    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None, None

    amount = float(match.group(1).replace(",", "."))
    currency = "EUR" if ("€" in text or "eur" in text) else None
    return amount, currency
