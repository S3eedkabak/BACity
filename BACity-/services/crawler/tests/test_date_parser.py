import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from crawler.extraction.date_parser import parse_event_datetime, parse_price


def test_iso8601():
    dt = parse_event_datetime("2026-08-28T20:00:00+02:00")
    assert dt.year == 2026 and dt.month == 8 and dt.day == 28 and dt.hour == 20


def test_slash_format():
    dt = parse_event_datetime("28/08/2026 20:00")
    assert dt.day == 28 and dt.month == 8 and dt.hour == 20


def test_english_at_format():
    dt = parse_event_datetime("Aug 28 2026 @ 8 PM")
    assert dt.month == 8 and dt.day == 28 and dt.hour == 20


def test_slovak_day_name_and_dot_format():
    dt = parse_event_datetime("Piatok 28. 8. od 20:00", reference_year=2026)
    assert dt.day == 28 and dt.month == 8 and dt.hour == 20


def test_slovak_full_date():
    dt = parse_event_datetime("28. 8. 2026, 20:00")
    assert dt.year == 2026 and dt.day == 28 and dt.month == 8 and dt.hour == 20


def test_garbage_returns_none():
    assert parse_event_datetime("not a date at all !!") is None


def test_empty_returns_none():
    assert parse_event_datetime("") is None
    assert parse_event_datetime(None) is None


def test_price_free_english():
    assert parse_price("Free") == (0.0, "EUR")


def test_price_free_slovak():
    assert parse_price("zdarma") == (0.0, "EUR")
    assert parse_price("voľný vstup") == (0.0, "EUR")


def test_price_euro_symbol():
    amount, currency = parse_price("€10")
    assert amount == 10.0 and currency == "EUR"


def test_price_comma_decimal():
    amount, currency = parse_price("7,50 EUR")
    assert amount == 7.5 and currency == "EUR"


def test_price_none():
    assert parse_price(None) == (None, None)
