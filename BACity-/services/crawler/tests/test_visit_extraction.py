from crawler.extraction.visit_extractor import extract_visit_events
from crawler.processing.normalize import normalize_event


def test_visit_uses_local_clock_not_midnight_metadata():
    html = '''<h1 itemprop="name">Concert</h1>
        <div class="event-date"><span class="start-date" content="2027-07-26T00:00:00+00:00">From 26 Jul</span>
        <span class="start-time">20:00</span><span class="end-date" content="2027-07-26T00:00:00+00:00"></span></div>
        <li class="address"><span class="value">Stadium</span></li>
        <div id="osm-map" data-lat="48.16" data-lng="17.13"></div>
        <div class="poster"><div style="background-image: url(https://example.org/event.jpg)"></div></div>'''
    event = normalize_event(extract_visit_events(html, 'https://www.visitbratislava.com/events/concert/')[0])
    assert event.start_time == '2027-07-26T20:00:00+02:00'
    assert event.end_time is None
    assert event.latitude == 48.16
    assert event.image_url == 'https://example.org/event.jpg'


def test_generic_microdata_venue_and_coordinates():
    from crawler.extraction.microdata_extractor import extract_microdata_events
    html = '''<article itemscope itemtype="https://schema.org/MusicEvent">
        <h1 itemprop="name">Music</h1><meta itemprop="startDate" content="2027-01-01T20:00:00+01:00">
        <div itemprop="location"><span itemprop="name">Club</span><span itemprop="address">Bratislava</span></div>
        <meta itemprop="latitude" content="48.15"><meta itemprop="longitude" content="17.12"></article>'''
    raw = extract_microdata_events(html, 'https://example.org/event')[0]
    assert raw.venue_name == 'Club'
    assert raw.latitude == 48.15
