"""Bounded hostile fixtures and mocked DNS only; no third-party probing."""
import asyncio
import json
import socket
from types import SimpleNamespace

import pytest
from scrapy import Request
from scrapy.exceptions import IgnoreRequest

from crawler.extraction.jsonld_extractor import extract_jsonld_events, MAX_EVENTS
from crawler.extraction.feeds import extract_feed


@pytest.mark.parametrize('host', ['127.1', '2130706433', '0x7f000001', '0177.0.0.1',
    '169.254.169.254', '[::1]', '[::ffff:127.0.0.1]', '[fd00::1]', '[fe80::1]',
    'rebind.example', 'xn--bacity-9za.example'])
def test_every_request_and_redirect_rejects_non_public_dns(monkeypatch, host):
    from crawler import middleware
    async def resolved(value):
        return value
    monkeypatch.setattr(middleware, 'deferToThread', lambda f: f())
    monkeypatch.setattr(middleware, 'maybe_deferred_to_future', resolved)
    # Include a public answer: ANY private answer must reject, not pick public.
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **kw: [
        (socket.AF_INET, 1, 6, '', ('93.184.216.34', 80)),
        (socket.AF_INET, 1, 6, '', ('127.0.0.1', 80))])
    with pytest.raises(IgnoreRequest):
        asyncio.run(middleware.PublicNetworkMiddleware().process_request(
            Request(f'http://{host}/events', meta={'redirect_times': 2}), SimpleNamespace()))


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'http://user:secret@public.example/events',
                               'https://public.example:8443/events', 'http://postgres/events'])
def test_url_policy_rejects_before_dns(monkeypatch, url):
    from crawler import middleware
    def forbidden_dns(*args, **kwargs):
        raise AssertionError('Rejected URL must not trigger DNS')
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden_dns)
    with pytest.raises(IgnoreRequest):
        asyncio.run(middleware.PublicNetworkMiddleware().process_request(Request(url), SimpleNamespace()))


def test_deep_json_and_wide_event_lists_are_bounded():
    event = {'@type': 'Event', 'name': 'Real fixture', 'startDate': '2030-01-02T20:00:00Z'}
    deep = '[' * 1500 + json.dumps(event) + ']' * 1500
    assert extract_jsonld_events('<script type="application/ld+json">' + deep + '</script>', 'https://public.example') == []
    moderate = '[' * 100 + json.dumps(event) + ']' * 100
    assert extract_jsonld_events('<script type="application/ld+json">' + moderate + '</script>', 'https://public.example') == []
    wide = json.dumps([event] * 5000)
    result = extract_jsonld_events('<script type="application/ld+json">' + wide + '</script>', 'https://public.example')
    assert len(result) == MAX_EVENTS
    assert extract_feed('x' * (2 * 1024 * 1024 + 1), 'https://public.example') == []
    assert extract_jsonld_events('x' * (5 * 1024 * 1024 + 1), 'https://public.example') == []


def test_entity_expansion_and_pathological_recurrence_fail_bounded():
    assert extract_feed('<!DOCTYPE rss [<!ENTITY a "boom">]><rss>&a;</rss>', 'https://public.example') == []
    ical = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Attack fixture\nDTSTART:20300102T200000Z\nRRULE:FREQ=SECONDLY;COUNT=999999999\nEND:VEVENT\nEND:VCALENDAR'
    assert extract_feed(ical, 'https://public.example') == []
