"""Synthetic website evidence, never scraped Instagram content or event proof."""
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from scrapy import Request
from scrapy.http import HtmlResponse

from crawler.instagram_discovery import (
    MAX_EVIDENCE_PER_PUBLISHER, MAX_PUBLISHERS,
    discover_profiles, profile_url, record_profiles,
)
from crawler.sources import ACTIVE_SOURCES
from crawler.spiders.discovery import DiscoverySpider, allowed_url
from crawler.state import State

SEED = next(s for s in ACTIVE_SOURCES if s.domain == 'novacvernovka.eu')


def page(html, url=SEED.event_url):
    return HtmlResponse(url, body=html.encode(), encoding='utf-8', request=Request(url))


@pytest.fixture
def state(tmp_path):
    value = State(str(tmp_path / 'state.db'))
    yield value
    value.close()


@pytest.mark.parametrize('url', [
    'https://instagram.com/Example_Hall',
    'https://WWW.INSTAGRAM.COM/example_hall/?utm_source=site#contact',
    'http://instagram.com./example_hall/',
])
def test_profile_identity_normalizes_host_case_and_tracking(url):
    assert profile_url(url) == 'https://www.instagram.com/example_hall/'


@pytest.mark.parametrize('url', [
    'https://instagram.com.attacker.example/hall/',
    'https://instagram.com@evil.example/hall/',
    'https://user:secret@instagram.com/hall/',
    'https://instagram.com:444/hall/',
    'https://instagram.com/p/announcement/',
    'https://instagram.com/reel/announcement/',
    'https://instagram.com/stories/hall/123/',
    'https://instagram.com/explore/',
    'https://instagram.com/direct/',
    'https://instagram.com//hall/',
    'https://instagram.com/hall//',
    'https://instagram.com/%68all/',
    'https://instagram.com/a..b/',
    'https://instagram.com/hall./',
    'https://instagram.com/' + 'a' * 31,
    'javascript:alert(1)', 'https://[invalid/', None,
])
def test_posts_routes_and_unsafe_links_are_not_publishers(url):
    assert profile_url(url) is None


def test_discovery_deduplicates_accounts_without_conferring_access(state, monkeypatch):
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('No network')))
    response = page('''<html><a href="https://instagram.com/Example_Hall/?utm_source=x">IG</a>
        <a href="//www.instagram.com/example_hall/">again</a>
        <a href="https://instagram.com/another_venue/">another</a>
        <a href="https://instagram.com/p/POST/">post</a></html>''')
    leads = discover_profiles(response, SEED, state.db)
    assert len(leads) == 2
    assert record_profiles(state.db, leads, now=1) == 2
    assert record_profiles(state.db, leads, now=2) == 0
    rows = state.db.execute('SELECT * FROM instagram_publishers ORDER BY handle').fetchall()
    assert len(rows) == 2  # Same platform host does not collapse distinct accounts.
    assert all(r['access_eligibility'] == 'authorization_required' for r in rows)
    assert all(r['last_collection_status'] == 'not_attempted' for r in rows)
    evidence = json.loads(rows[0]['evidence'])
    assert evidence[0]['url'] == SEED.event_url
    assert evidence[0]['relationship'] == 'site_declared_profile'
    assert evidence[0]['relevance_basis'] == 'bacity_registered_bratislava_source'
    assert rows[0]['last_seen'] == 2
    assert state.db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 0
    assert state.db.execute('SELECT count(*) FROM sources').fetchone()[0] == 0


@pytest.mark.parametrize('url', [
    'https://unrelated.example/events', 'https://127.0.0.1/events',
    'https://novacvernovka.eu/program?access_token=secret',
])
def test_unrelated_redirects_and_sensitive_evidence_are_ignored(state, url):
    assert discover_profiles(page('<a href="https://instagram.com/hall/">IG</a>', url), SEED, state.db) == []


def test_unknown_sources_need_qualified_local_evidence(state):
    seed = replace(SEED, domain='hall.example', base_url='https://hall.example', event_url='https://hall.example/events')
    response = page('<a href="https://instagram.com/hall/">IG</a>', seed.event_url)
    assert discover_profiles(response, seed, state.db) == []
    state.discover(seed.event_url, SEED.event_url)
    for status, observations in [('discovered', 0), ('probation', 0), ('disabled', 5), ('blocked', 5)]:
        with state.db:
            state.db.execute('UPDATE candidates SET status=?,qualified_observations=?', (status, observations))
        assert discover_profiles(response, seed, state.db) == []
    with state.db:
        state.db.execute("UPDATE candidates SET status='trusted',qualified_observations=3")
    leads = discover_profiles(response, seed, state.db)
    assert len(leads) == 1
    assert leads[0].relevance_basis == 'bacity_qualified_local_source'


def test_malformed_href_does_not_discard_good_evidence(state):
    response = page('<a href="https://[bad/">bad</a><a href="https://instagram.com/hall/">IG</a>')
    assert len(discover_profiles(response, SEED, state.db)) == 1


def test_profile_and_provenance_growth_is_bounded(state):
    response = page(''.join(f'<a href="https://instagram.com/hall{i}/">IG</a>' for i in range(50)))
    leads = discover_profiles(response, SEED, state.db)
    assert len(leads) == 10
    lead = leads[0]
    for i in range(10):
        record_profiles(state.db, [replace(lead, evidence_url=f'https://novacvernovka.eu/program/{i}')])
    evidence = json.loads(state.db.execute('SELECT evidence FROM instagram_publishers').fetchone()[0])
    assert len(evidence) == MAX_EVIDENCE_PER_PUBLISHER
    for i in range(MAX_PUBLISHERS + 5):
        record_profiles(state.db, [replace(lead, profile_url=f'https://www.instagram.com/venue{i}/')])
    assert state.db.execute('SELECT count(*) FROM instagram_publishers').fetchone()[0] == MAX_PUBLISHERS
    assert record_profiles(state.db, [lead], now=9999999999) == 0  # Known identities still refresh at capacity.


def test_registry_rollback_on_invalid_identity(state):
    lead = discover_profiles(page('<a href="https://instagram.com/hall/">IG</a>'), SEED, state.db)[0]
    with pytest.raises(ValueError):
        record_profiles(state.db, [lead, replace(lead, profile_url='https://evil.example/hall/')])
    assert state.db.execute('SELECT count(*) FROM instagram_publishers').fetchone()[0] == 0


def test_disabled_hook_does_not_open_state_or_add_work(monkeypatch):
    monkeypatch.delenv('L4_INSTAGRAM_DISCOVERY_ENABLED', raising=False)
    monkeypatch.setattr('crawler.spiders.discovery.State', Mock(side_effect=AssertionError('No state')))
    spider = DiscoverySpider(source=SEED)
    spider._observe_instagram_profiles(page('<html></html>'), SEED)
    assert spider.state is None


def test_enabled_hook_records_leads_only_and_does_not_unblock_instagram(state, monkeypatch):
    monkeypatch.setenv('L4_INSTAGRAM_DISCOVERY_ENABLED', '1')
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('No network')))
    spider = DiscoverySpider(source=SEED)
    spider.state = state
    spider.crawler = SimpleNamespace(stats=Mock())
    response = page('<a href="https://instagram.com/hall/">IG</a>')
    spider._observe_instagram_profiles(response, SEED)
    assert state.db.execute('SELECT count(*) FROM instagram_publishers').fetchone()[0] == 1
    assert state.db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 0
    assert not allowed_url('https://instagram.com/hall/')
    assert not allowed_url('https://instagram.com/p/POST/')
    spider.crawler.stats.inc_value.assert_any_call('instagram/accounts_discovered', 1)


def test_optional_failure_isolated_from_existing_crawl(state, monkeypatch):
    monkeypatch.setenv('L4_INSTAGRAM_DISCOVERY_ENABLED', '1')
    monkeypatch.setattr('crawler.instagram_discovery.record_profiles', Mock(side_effect=RuntimeError('private detail')))
    spider = DiscoverySpider(source=SEED)
    spider.state = state
    spider.crawler = SimpleNamespace(stats=Mock())
    spider._observe_instagram_profiles(page('<a href="https://instagram.com/hall/">IG</a>'), SEED)
    spider.crawler.stats.inc_value.assert_called_with('instagram/discovery_errors')


def test_existing_parse_still_yields_events_and_never_follows_instagram(state, monkeypatch):
    monkeypatch.setenv('L4_INSTAGRAM_DISCOVERY_ENABLED', '1')
    spider = DiscoverySpider(source=SEED)
    spider.state = state
    spider.crawler = SimpleNamespace(stats=Mock())
    existing_event = object()
    spider._extract = lambda *_: iter([existing_event])
    response = page('''<html><a href="https://instagram.com/hall/">IG</a>
        <a href="/program/local-concert">Concert</a></html>''')
    response.request.meta.update(source=SEED, crawl_depth=0)
    output = list(spider.parse(response))
    assert output[0] is existing_event
    requests = [item for item in output if isinstance(item, Request)]
    assert [request.url for request in requests] == ['https://novacvernovka.eu/program/local-concert']
    assert state.db.execute('SELECT count(*) FROM instagram_publishers').fetchone()[0] == 1
    assert state.db.execute('SELECT count(*) FROM outbox').fetchone()[0] == 0
