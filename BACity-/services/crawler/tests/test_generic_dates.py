"""Regression cases for numbered A4 titles mistaken for event dates."""
import pytest
from crawler.extraction.date_parser import parse_event_datetime
from crawler.extraction.generic_extractor import extract_generic_html, extract_event_cards, extract_opengraph_event
from crawler.processing.normalize import normalize_event


@pytest.mark.parametrize('text', ['26. Zápisky', '1. REPRÍZA', '26. market', '19:00', 'September', '31. 2. 2026'])
def test_incomplete_or_impossible_dates_are_rejected(text):
    assert parse_event_datetime(text, reference_year=2026) is None


@pytest.mark.parametrize('title', ['26. Zápisky', '1. REPRÍZA'])
def test_numbered_title_does_not_mask_real_date(title):
    html = f'<h1>{title}</h1><div class="event-date">24. 9. 2026, 19:00</div><div class="venue">A4</div>'
    raw = extract_generic_html(html, 'https://a4.sk/event/example/')[0]
    event = normalize_event(raw)
    assert event.start_time.startswith('2026-09-24T19:00:00')
    assert event.title == title


def test_explicit_machine_date_beats_title_and_unrelated_body_date():
    html = '<h1>26. Zápisky</h1><p>Published 1. 1. 2020</p><time datetime="2026-09-24T19:30:00+02:00">Štvrtok</time>'
    raw = extract_generic_html(html, 'https://a4.sk/event/example/')[0]
    assert raw.start_raw == '2026-09-24T19:30:00+02:00'


def test_listing_card_uses_event_date_without_title_date_false_positive():
    html = '<article><h2><a href="/event/one">1. REPRÍZA</a></h2><time datetime="2026-10-01T20:00:00+02:00"></time></article>'
    events = extract_event_cards(html, 'https://a4.sk/program/')
    assert len(events) == 1
    assert events[0].start_raw == '2026-10-01T20:00:00+02:00'
    assert events[0].source_url == 'https://a4.sk/event/one'


def test_numbered_title_alone_is_not_an_event():
    html = '<meta property="og:title" content="26. Zápisky"><article><h1>26. Zápisky</h1><p>1. REPRÍZA</p></article>'
    assert extract_generic_html(html, 'https://a4.sk/event/example/') == []
    assert extract_event_cards(html, 'https://a4.sk/program/') == []
    assert extract_opengraph_event(html, 'https://a4.sk/event/example/') is None


def test_slash_and_english_dates_keep_explicit_day_and_month():
    assert parse_event_datetime('24/09/2026 19:00').isoformat().startswith('2026-09-24T19:00')
    assert parse_event_datetime('24 September 2026 19:00').isoformat().startswith('2026-09-24T19:00')
