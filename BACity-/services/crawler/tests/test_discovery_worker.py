import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from scrapy import Request
from scrapy.http import HtmlResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crawler.sources import ACTIVE_SOURCES
from crawler.state import State
from crawler.worker import deliver
from crawler.spiders.discovery import DiscoverySpider, allowed_url
from crawler.extraction.jsonld_extractor import extract_jsonld_events
from crawler.processing.normalize import normalize_event
from crawler.processing.validate import validate_event
from crawler.pipelines import GeocodePipeline


def test_restart_preserves_schedule_backoff_and_history(tmp_path):
    path = str(tmp_path / 'state.db')
    state = State(path)
    seed = ACTIVE_SOURCES[0]
    state.seed(seed)
    run = state.begin(seed.domain)
    assert state.finish(run, seed, False, {'rejected': 2}) == 1
    assert not state.due()
    state.close()
    state = State(path)
    row = state.db.execute('SELECT * FROM sources').fetchone()
    assert row['failures'] == 1
    assert state.db.execute('SELECT success FROM runs').fetchone()[0] == 0
    run = state.begin(seed.domain)
    state.finish(run, seed, True, {'accepted': 1})
    assert state.db.execute('SELECT failures FROM sources').fetchone()[0] == 0
    state.close()


def test_runtime_source_disable_and_frequency_are_allow_listed(tmp_path):
    state = State(str(tmp_path / 'state.db'))
    seed = ACTIVE_SOURCES[0]
    state.seed(seed)
    state.apply_runtime_config([{'domain': seed.domain, 'enabled': False, 'crawl_frequency_minutes': 30},
                                {'domain': 'untrusted.example', 'enabled': True, 'crawl_frequency_minutes': 1}])
    assert state.due() == []
    stored = json.loads(state.db.execute('SELECT seed FROM sources WHERE domain=?', (seed.domain,)).fetchone()[0])
    assert stored['crawl_frequency_minutes'] == 30
    assert state.db.execute('SELECT count(*) FROM sources').fetchone()[0] == 1
    state.close()


def test_outbox_survives_api_failure_and_restarts(tmp_path, monkeypatch):
    path = str(tmp_path / 'state.db')
    state = State(path)
    payload = {'source_url': 'https://example.org/event/1', 'title': 'Concert', 'start_time': '2027-01-01T20:00:00Z'}
    state.enqueue(payload)
    state.enqueue(payload)
    monkeypatch.setattr(requests, 'post', Mock(side_effect=requests.ConnectionError('offline')))
    assert deliver(state, 'http://api') == 0
    state.close()
    state = State(path)
    assert state.db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 1
    post = Mock(return_value=Mock(raise_for_status=lambda: None))
    monkeypatch.setattr(requests, 'post', post)
    with state.db:
        state.db.execute('UPDATE outbox SET next_try=0')
    assert deliver(state, 'http://api', 'secret') == 1
    assert post.call_args.kwargs['headers']['X-Ingestion-Key'] == 'secret'
    assert state.db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 0
    state.close()


def test_discovery_scans_beyond_navigation_and_finds_external_sources(tmp_path, monkeypatch):
    monkeypatch.setenv('CRAWLER_STATE_PATH', str(tmp_path / 'state.db'))
    spider = DiscoverySpider(source=ACTIVE_SOURCES[0])
    spider.crawler = SimpleNamespace(stats=Mock())
    html = '<a href="/about">About</a>' * 30 + '''
        <a href="/events/concert">Concert</a><a rel="next" href="/events/?page=2">Next</a>
        <a href="https://new-venue.example/program">Program</a>
        <a href="https://facebook.com/events/1">Event</a>'''
    request = Request('https://www.visitbratislava.com/events/', meta={'source': ACTIVE_SOURCES[0]})
    response = HtmlResponse(request.url, body=html.encode(), encoding='utf-8', request=request)
    found = [x for x in spider.parse(response) if isinstance(x, Request)]
    assert len(found) == 2
    assert any('page=2' in x.url for x in found)
    rows = spider.state.db.execute('SELECT domain,discovered_from FROM sources').fetchall()
    assert [r['domain'] for r in rows] == ['new-venue.example']
    assert rows[0]['discovered_from'] == request.url
    spider.closed('finished')


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'http://user:password@example.com', 'https://facebook.com/events', 'https://example.org:3000/events'])
def test_domain_policy(url):
    assert not allowed_url(url)


def test_nested_jsonld_normalization_free_address_and_cancelled():
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    node = {'@type': 'ItemList', 'itemListElement': [{'item': {
        '@type': 'https://schema.org/MusicEvent', 'name': '<b> Jazz   Night </b>',
        'startDate': start, 'url': '/event/jazz?utm_source=news',
        'image': {'url': '/jazz.jpg'}, 'isAccessibleForFree': True,
        'eventStatus': 'https://schema.org/EventCancelled',
        'location': {'name': 'Club', 'address': {'streetAddress': 'Street 1', 'addressLocality': 'Bratislava'},
                     'geo': {'latitude': 48.15, 'longitude': 17.11}}}}]}
    raw = extract_jsonld_events('<script type="application/ld+json">' + json.dumps(node) + '</script>', 'https://example.org/events')[0]
    event = normalize_event(raw)
    assert event.title == 'Jazz Night'
    assert event.price == 0
    assert event.source_url == 'https://example.org/event/jazz'
    assert event.image_url == 'https://example.org/jazz.jpg'
    assert event.address == 'Street 1, Bratislava'
    assert event.event_status == 'cancelled'
    assert validate_event(event).accepted
    event.latitude = 49.1
    assert not validate_event(event).accepted


def test_geocoding_is_persistent_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv('CRAWLER_STATE_PATH', str(tmp_path / 'geo.db'))
    settings = {'GEOCODER_URL': 'https://geo.example/search', 'GEOCODER_USER_AGENT': 'test'}
    spider = SimpleNamespace(settings=settings)
    get = Mock(return_value=Mock(raise_for_status=lambda: None, json=lambda: [{'lat': '48.15', 'lon': '17.12'}]))
    monkeypatch.setattr(requests, 'get', get)
    def item():
        return SimpleNamespace(venue_name='Test Hall', address='Street 9, Bratislava', latitude=None, longitude=None)
    first = GeocodePipeline()
    first.open_spider(spider)
    assert first.process_item(item(), spider).latitude == 48.15
    first.close_spider(spider)
    second = GeocodePipeline()
    second.open_spider(spider)
    assert second.process_item(item(), spider).longitude == 17.12
    assert get.call_count == 1
    assert get.call_args.kwargs['params']['bounded'] == 1
    second.close_spider(spider)


def test_rejected_payload_does_not_block_valid_queue_items(tmp_path, monkeypatch):
    state = State(str(tmp_path / 'queue.db'))
    state.enqueue({'source_url': 'https://example.org/a', 'title': 'A', 'start_time': '2027-01-01'})
    state.enqueue({'source_url': 'https://example.org/b', 'title': 'B', 'start_time': '2027-01-01'})
    response = requests.Response()
    response.status_code = 422
    post = Mock(side_effect=[Mock(raise_for_status=Mock(side_effect=requests.HTTPError('invalid', response=response))), Mock(raise_for_status=lambda: None)])
    monkeypatch.setattr(requests, 'post', post)
    assert deliver(state, 'http://api') == 1
    assert state.db.execute('SELECT status FROM outbox').fetchone()[0] == 'rejected'
    state.close()


def test_network_policy_rejects_private_addresses(monkeypatch):
    from crawler import middleware
    from scrapy.exceptions import IgnoreRequest
    monkeypatch.setattr(middleware, 'deferToThread', lambda f: f())
    monkeypatch.setattr(middleware.socket, 'getaddrinfo', lambda *a, **kw: [(2, 1, 6, '', ('127.0.0.1', 80))])
    with pytest.raises(IgnoreRequest):
        middleware.PublicNetworkMiddleware().process_request(Request('https://venue.example/events'), SimpleNamespace())


def test_robots_crawl_delay_survives_later_responses():
    from crawler.middleware import PublicNetworkMiddleware
    slot = SimpleNamespace(delay=1.5)
    spider = SimpleNamespace(settings={'USER_AGENT': 'BACityBot'}, crawler=SimpleNamespace(engine=SimpleNamespace(downloader=SimpleNamespace(slots={'example.org': slot}))))
    middleware = PublicNetworkMiddleware()
    req = Request('https://example.org/robots.txt')
    response = HtmlResponse(req.url, body=b'User-agent: *\nCrawl-delay: 20\n', encoding='utf-8', request=req)
    middleware.process_response(req, response, spider)
    assert slot.delay == 20
    slot.delay = 2
    req = Request('https://example.org/events')
    middleware.process_response(req, HtmlResponse(req.url, request=req), spider)
    assert slot.delay == 20


def test_worker_lock_prevents_overlap(tmp_path):
    from filelock import FileLock, Timeout
    lock = str(tmp_path / 'worker.lock')
    with FileLock(lock):
        with pytest.raises(Timeout):
            with FileLock(lock, timeout=0):
                raise AssertionError('second worker acquired the lock')
