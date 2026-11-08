from datetime import datetime

from crawler.extraction.community_extractors import extract_cvernovka_events, extract_karlova_ves_events
from crawler.processing.normalize import normalize_event


def test_cvernovka_cards_use_explicit_date_and_clean_title():
    html = '''<article class="hk_event" data-start="20261003">
      <a href="/program/linoryt"><div class="FilterItem__date-container"><div>03/10</div><div>sobota</div><div>10:00</div></div>
      <h3 class="entry-title">Linorytový kurz 2</h3><div class="entry-content">Tvorivý workshop.</div>
      <span class="tag">#workshop</span><img src="/poster.jpg"></a></article>'''
    raw = extract_cvernovka_events(html, "https://novacvernovka.eu/program")
    assert len(raw) == 1
    assert raw[0].title == "Linorytový kurz 2"
    assert raw[0].start_raw == "2026-10-03 10:00"
    assert raw[0].source_url == "https://novacvernovka.eu/program/linoryt"
    assert normalize_event(raw[0]).start_time.startswith("2026-10-03T10:00:00")


def test_karlova_ves_api_maps_coordinates_and_ignores_malformed_rows():
    data = {"data": [{"id": 7, "slug": "concert-7", "title": "Komorný koncert",
                      "description": "<p>Hudba v Karlovej Vsi.</p>",
                      "start_date": "2026-10-20T18:00:00+02:00", "end_date": "2026-10-20T20:00:00+02:00",
                      "location": "KCK", "lat": "48.15", "lng": "17.06", "is_paid": False,
                      "poster_image": "/storage/poster.png"}, {"title": "Missing date"}]}
    events = extract_karlova_ves_events(data, "https://kultura.karlovaves.sk/api/events/all?per_page=100")
    assert len(events) == 1
    event = normalize_event(events[0])
    assert event.latitude == 48.15 and event.longitude == 17.06
    assert event.price == 0
    assert event.source_url.endswith("/podujatie/concert-7")


def test_numbered_title_is_not_used_as_event_date():
    html = '<article class="hk_event"><h3 class="entry-title">26. Zápisky z mesta</h3></article>'
    assert extract_cvernovka_events(html, "https://novacvernovka.eu/program") == []
