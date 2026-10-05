import asyncio
import json
import socket
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from scrapy import Request
from scrapy.exceptions import IgnoreRequest

from crawler.discovery import candidate_url, assess
from crawler.extraction.temporal import interval
from crawler.extraction.feeds import extract_feed
from crawler.processing.normalize import normalize_event
from crawler.state import State


@pytest.mark.parametrize('start,end,duration,hours,evidence', [
    ('2027-01-02T19:00:00+01:00','22:00',None,3,'explicit_end'),
    ('2027-01-02T23:00:00+01:00','01:00',None,2,'explicit_end'),
    ('2027-01-02T19:00:00+01:00','2027-01-04T19:00:00+01:00',None,48,'explicit_end'),
    ('2027-01-02T19:00:00+01:00',None,'PT90M',1.5,'explicit_duration'),
    ('2. januára 2027 19.00 – 22.00',None,None,3,'text_range'),
    ('2027-01-02 19:00 – 2027-01-04 19:00',None,None,48,'text_range'),
    ('2027-03-28T01:30:00+01:00','2027-03-28T03:30:00+02:00',None,1,'explicit_end'),
])
def test_explicit_temporal_intervals(start,end,duration,hours,evidence):
    a,b,reason=interval(start,end,duration)
    assert a and b and (b-a).total_seconds() == hours*3600
    assert reason == evidence


@pytest.mark.parametrize('end,duration',[ (None,None), (None,'concert 2 hours'), ('nonsense',None), ('2027-01-01T12:00:00Z',None), (None,'P9999D') ])
def test_missing_or_invalid_end_is_never_invented(end,duration):
    assert interval('2027-01-02T19:00:00Z',end,duration)[1] is None


@pytest.mark.parametrize('start',['2027-03-28 02:30','2027-10-31 02:30'])
def test_ambiguous_or_nonexistent_local_start_rejected(start):
    assert interval(start)[0] is None


def test_jsonld_duration_organizer_and_doors_not_used_as_start():
    node={'@type':'Event','name':'Concert','startDate':'2027-01-02T20:00:00+01:00',
          'doorTime':'2027-01-02T18:00:00+01:00','duration':'PT90M','organizer':{'name':'Music Hall'}}
    raw=extract_feed('<html><script type="application/ld+json">'+json.dumps(node)+'</script></html>','https://hall.example/events')[0]
    event=normalize_event(raw)
    assert event.temporal_evidence == 'explicit_duration'
    assert event.organizer_name == 'Music Hall'
    assert '20:00' in event.start_time and '21:30' in event.end_time


@pytest.mark.parametrize('tag',['item','entry'])
def test_feed_publication_date_is_not_event_date(tag):
    xml=f'<feed><{tag}><title>News</title><pubDate>2027-01-02T20:00:00Z</pubDate></{tag}></feed>'
    assert extract_feed(xml,'https://hall.example/rss') == []
    xml=f'<feed><{tag}><title>Music</title><startDate>2027-01-02T20:00:00Z</startDate><endDate>2027-01-02T22:00:00Z</endDate><link href="/music"/></{tag}></feed>'
    event=normalize_event(extract_feed(xml,'https://hall.example/rss')[0])
    assert event.end_time and event.source_url == 'https://hall.example/music'


def test_ical_recurrence_exclusions_and_resource_bounds():
    text='BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Weekly Jazz\nDTSTART;TZID=Europe/Bratislava:20270102T200000\nDTEND;TZID=Europe/Bratislava:20270102T220000\nRRULE:FREQ=WEEKLY;COUNT=4\nEXDATE;TZID=Europe/Bratislava:20270109T200000\nEND:VEVENT\nEND:VCALENDAR'
    result=extract_feed(text,'https://hall.example/events.ics',datetime(2027,1,1,tzinfo=timezone.utc))
    assert len(result) == 3 and len({x.start_raw for x in result}) == 3
    assert all(normalize_event(x).end_time for x in result)
    assert extract_feed(text.replace('FREQ=WEEKLY;COUNT=4','FREQ=SECONDLY'),'https://hall.example/events.ics') == []
    assert extract_feed('<!DOCTYPE rss [<!ENTITY x "boom">]><rss/>','https://hall.example/rss') == []


@pytest.mark.parametrize('url',['http://127.0.0.1/events','http://10.0.0.1/events','http://169.254.169.254/events','http://postgres/events','http://site.internal/events','file:///tmp/events','https://user:pass@site.example/events','https://site.example/events?token=secret'])
def test_candidate_ssrf_and_credential_policy(url):
    with pytest.raises(ValueError):
        candidate_url(url)


def test_candidates_dedupe_probation_trust_demotion_and_bounds(tmp_path):
    state=State(str(tmp_path/'state.db'))
    state.discover('https://www.hall.example/events?utm_source=test','https://city.example/events')
    state.discover('https://hall.example/calendar','https://city.example/events')
    assert state.db.execute('SELECT count(*) FROM candidates').fetchone()[0] == 1
    stats={'quality/events':5,'quality/score_total':400,'validation/rejected':0}
    for expected in ('probation','probation','trusted'):
        state.candidate_result('hall.example',stats,True)
        assert state.db.execute('SELECT status FROM candidates').fetchone()[0] == expected
    state.candidate_result('hall.example',{'quality/events':5,'quality/score_total':50},True)
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0] == 'probation'
    state.candidate_result('hall.example',{'robotstxt/forbidden':1},False)
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0] == 'blocked'
    for i in range(260):
        state.discover(f'https://hall{i}.example/events','https://city.example/events')
    assert state.db.execute('SELECT count(*) FROM candidates').fetchone()[0] == 250
    assert len(state.inspect_due()) <= 5
    with pytest.raises(ValueError):
        state.discover('https://hall.example/events','https://city.example/events',public=False)
    state.close()


def test_failure_qualification():
    assert assess(3,0,3,{}) == ('rejected','consecutive_failures')
    assert assess(3,0,0,{}) == ('rejected','no_valid_events')


def test_visit_date_only_end_does_not_invent_closing_time():
    from crawler.extraction.visit_extractor import extract_visit_events
    html='<h1 class="title">Festival</h1><div class="event-date"><span class="start-date" content="2027-01-02"></span><span class="start-time">19:00</span><span class="end-date" content="2027-01-04"></span></div>'
    assert extract_visit_events(html,'https://www.visitbratislava.com/events/festival')[0].end_raw is None


def test_json_api_is_not_traversed_as_html():
    from scrapy.http import TextResponse
    from crawler.sources import ACTIVE_SOURCES
    from crawler.spiders.discovery import DiscoverySpider
    source=next(s for s in ACTIVE_SOURCES if s.parser=='karlova_ves_api')
    spider=DiscoverySpider(source=source)
    response=TextResponse(source.event_url,body=b'[]',encoding='utf-8',headers={'Content-Type':'application/json'},request=Request(source.event_url,meta={'source':source}))
    assert list(spider.parse(response)) == []


def test_redirect_dns_guard_and_pinned_connection(monkeypatch):
    from crawler import middleware
    async def resolved(value):
        return value
    monkeypatch.setattr(middleware,'deferToThread',lambda f:f())
    monkeypatch.setattr(middleware,'maybe_deferred_to_future',resolved)
    monkeypatch.setattr(middleware.socket,'getaddrinfo',lambda *a,**kw:[(socket.AF_INET,1,6,'',('93.184.216.34',80))])
    guard=middleware.PublicNetworkMiddleware()
    asyncio.run(guard.process_request(Request('https://public.example/events'),SimpleNamespace()))
    assert middleware.dnscache['public.example'] == '93.184.216.34'
    # Redirects run through exactly the same guard; DNS changes fail closed.
    monkeypatch.setattr(middleware.socket,'getaddrinfo',lambda *a,**kw:[(socket.AF_INET,1,6,'',('192.168.0.1',80))])
    with pytest.raises(IgnoreRequest):
        asyncio.run(guard.process_request(Request('https://public.example/private',meta={'redirect_times':1}),SimpleNamespace()))


def test_rendering_requires_public_only_egress_and_invalid_end_retains_start(monkeypatch):
    from crawler.middleware import PublicNetworkMiddleware
    monkeypatch.delenv('CRAWLER_RENDER_NETWORK_ISOLATED',raising=False)
    with pytest.raises(IgnoreRequest):
        asyncio.run(PublicNetworkMiddleware().process_request(Request('https://hall.example/events',meta={'playwright':True}),SimpleNamespace()))
    start,end,_=interval('2027-03-28T00:30:00+01:00','02:30')
    assert start is not None and end is None


def test_shared_month_range_preserves_start_without_inventing_end():
    start,end,_=interval('2. – 4. októbra 2027')
    assert start and start.day == 2 and start.month == 10 and end is None


def test_trusted_candidate_still_requires_bratislava_evidence():
    from crawler.items import RawEvent
    from crawler.pipelines import ValidatePipeline
    from scrapy.exceptions import DropItem
    from unittest.mock import Mock
    event=normalize_event(RawEvent(title='Music',start_raw='2027-01-02T20:00:00Z',
        venue_name='Foreign Hall',source_url='https://hall.example/events',source_reliability=.75,extraction_confidence=.9))
    spider=SimpleNamespace(sources=[SimpleNamespace(parser='structured')],crawler=SimpleNamespace(stats=Mock()))
    with pytest.raises(DropItem):
        ValidatePipeline().process_item(event,spider)


def test_direct_jsonld_and_failed_source_are_not_false_success():
    raw=extract_feed(json.dumps({'@type':'Event','name':'Concert','startDate':'2027-01-02T20:00:00Z'}),'https://hall.example/events')
    assert len(raw) == 1
    from crawler.run import successful
    stats={'finish_reason':'finished','response_received_count':2}
    assert successful(stats,[])
    assert not successful({**stats,'source/request_errors':1},[])
    assert not successful({**stats,'extraction/errors':1},[])
