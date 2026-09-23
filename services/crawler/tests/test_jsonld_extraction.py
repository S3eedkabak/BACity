import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.extraction.jsonld_extractor import extract_jsonld_events

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_extracts_music_event():
    html = (FIXTURES / "event_jsonld_techno_night.html").read_text()
    events = extract_jsonld_events(html, "https://example.com/techno")
    assert len(events) == 1
    e = events[0]
    assert e.title == "Techno Night"
    assert e.start_raw == "2026-08-29T22:00:00+02:00"
    assert e.venue_name == "Fuga"
    assert "10" in e.price_raw
    assert e.extraction_method == "jsonld"
    assert e.extraction_confidence >= 0.9


def test_extracts_free_event():
    html = (FIXTURES / "event_jsonld_jazz_free.html").read_text()
    events = extract_jsonld_events(html, "https://example.com/jazz")
    assert len(events) == 1
    assert events[0].title == "Jazz Under the Stars"
    assert events[0].price_raw.startswith("0")


def test_no_jsonld_returns_empty():
    html = (FIXTURES / "event_slovak_generic_html.html").read_text()
    events = extract_jsonld_events(html, "https://example.com/x")
    assert events == []


def test_malformed_jsonld_does_not_crash():
    html = '<script type="application/ld+json">{not valid json</script>'
    events = extract_jsonld_events(html, "https://example.com/broken")
    assert events == []
