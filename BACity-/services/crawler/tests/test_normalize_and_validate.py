import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.items import RawEvent
from crawler.processing.normalize import normalize_event, guess_category
from crawler.processing.validate import validate_event


def test_normalize_valid_event():
    raw = RawEvent(
        title="Techno Night",
        start_raw="2026-08-29T22:00:00+02:00",
        description="Techno all night.",
        venue_name="Fuga",
        price_raw="€10",
        source_url="https://example.com",
        extraction_confidence=0.9,
    )
    n = normalize_event(raw)
    assert n is not None
    assert n.price == 10.0
    assert n.category == "Nightlife"


def test_normalize_unparseable_date_returns_none():
    raw = RawEvent(title="Mystery", start_raw="not a date", source_url="https://example.com")
    assert normalize_event(raw) is None


def test_guess_category_student():
    assert guess_category("Student Welcome Party", None, None) == "Student"


def test_guess_category_falls_back_to_other():
    assert guess_category("Untitled Gathering", None, None) == "Other"


def test_validate_rejects_past_event():
    raw = RawEvent(title="Old show", start_raw="2020-01-01T20:00:00+01:00",
                    source_url="https://example.com", extraction_confidence=0.9)
    n = normalize_event(raw)
    result = validate_event(n)
    assert not result.accepted
    assert "past" in result.reason


def test_validate_rejects_low_confidence():
    raw = RawEvent(title="Sketchy event", start_raw="2026-12-01T20:00:00+01:00",
                    source_url="https://example.com", extraction_confidence=0.1)
    n = normalize_event(raw)
    result = validate_event(n)
    assert not result.accepted


def test_validate_flags_medium_confidence_for_advanced_extraction():
    raw = RawEvent(title="Fuzzy event", start_raw="2026-12-01T20:00:00+01:00",
                    source_url="https://example.com", extraction_confidence=0.4)
    n = normalize_event(raw)
    result = validate_event(n)
    assert result.accepted
    assert result.needs_advanced_extraction


def test_validate_accepts_high_confidence_future_event():
    raw = RawEvent(title="Great Concert", start_raw="2026-12-01T20:00:00+01:00",
                    source_url="https://example.com", extraction_confidence=0.9)
    n = normalize_event(raw)
    result = validate_event(n)
    assert result.accepted
    assert not result.needs_advanced_extraction
