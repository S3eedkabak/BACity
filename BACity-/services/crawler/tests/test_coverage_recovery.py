import json
import time
from types import SimpleNamespace
from unittest.mock import Mock
from dataclasses import replace

import pytest
from scrapy import Request
from scrapy.http import HtmlResponse
from crawler.sources import ACTIVE_SOURCES, SourceSeed
from crawler.spiders.discovery import DiscoverySpider
from crawler.extraction.source_html import extract_source_html
from crawler.navigation import navigation_url
from crawler.processing.normalize import normalize_event
from crawler.state import State


def test_visit_listing_is_discovery_not_incomplete_event():
    seed=ACTIVE_SOURCES[0]
    spider=DiscoverySpider(source=seed)
    spider.crawler=SimpleNamespace(stats=Mock())
    html='<article><h2><a href="/events/concert/">Concert</a></h2><time datetime="2027-01-02T00:00:00Z"></time></article>'
    response=HtmlResponse(seed.event_url,body=html.encode(),encoding='utf-8',request=Request(seed.event_url,meta={'source':seed}))
    results=list(spider.parse(response))
    assert len(results)==1 and isinstance(results[0],Request)
    assert results[0].url.endswith('/events/concert/')


def test_visit_actual_detail_retains_clock_and_place():
    from crawler.extraction.visit_extractor import extract_visit_events
    html='''<h1 class="title" itemprop="name">Berlin Manson</h1><div class="event-date">
    <span class="start-date" content="2027-10-22T00:00:00+00:00"></span><span class="start-time">19:00</span>
    <span class="end-date" content="2027-10-22T00:00:00+00:00"></span></div>
    <li class="address"><span class="value">STARS auditorium</span></li><div id="osm-map" data-lat="48.1676" data-lng="17.1424"></div>'''
    e=normalize_event(extract_visit_events(html,'https://www.visitbratislava.com/events/berlin-manson/')[0])
    assert e.start_time=='2027-10-22T19:00:00+02:00' and e.end_time is None
    assert e.venue_name=='STARS auditorium' and e.latitude==48.1676


def test_sng_nested_absolute_links_are_repaired_and_other_sites_excluded():
    u='https://www.sng.sk/en/slovak-national-gallery/whatson/en/slovak-national-gallery/events/network'
    assert navigation_url(u,'sng.sk')=='https://www.sng.sk/en/slovak-national-gallery/events/network'
    assert navigation_url('https://sng.sk/sk/sng-bratislava/stranka/kontakt','sng.sk') is None


def test_cvernovka_archive_not_followed():
    assert navigation_url('https://novacvernovka.eu/program/archiv','novacvernovka.eu') is None
    seed=next(s for s in ACTIVE_SOURCES if s.parser=='cvernovka')
    spider=DiscoverySpider(source=seed);spider.crawler=SimpleNamespace(stats=Mock())
    url=seed.event_url+'/concert'
    html='<a href="/program/old-concert">Old concert</a><a href="/program/archiv">Program archive</a>'
    response=HtmlResponse(url,body=html.encode(),encoding='utf-8',request=Request(url,meta={'source':seed}))
    assert not any(isinstance(x,Request) for x in spider.parse(response))


def test_pagination_does_not_spend_event_detail_depth():
    seed=ACTIVE_SOURCES[0];spider=DiscoverySpider(source=seed);spider.crawler=SimpleNamespace(stats=Mock())
    html='<a rel="next" href="/event/page/4/">Next</a><a href="/events/concert/">Concert</a>'
    response=HtmlResponse(seed.event_url,body=html.encode(),encoding='utf-8',request=Request(seed.event_url,meta={'source':seed,'crawl_depth':3}))
    found=list(spider.parse(response))
    assert len(found)==1 and found[0].meta['crawl_depth']==3
    assert found[0].url.endswith('/event/page/4/')


def test_a4_html_uses_event_permalink_and_own_header_only():
    html='''<div><div>sobota o 19:00</div><h1>IMAGO SONORIS</h1></div>
    <div><p>A4</p><p>Karpatská 2 (budova YMCA)</p><p>811 05 Bratislava 1</p></div>'''
    url='https://a4.sk/events/2027/10/24/imago-sonoris/'
    raw=extract_source_html(html,url)[0];e=normalize_event(raw)
    assert e.start_time=='2027-10-24T19:00:00+02:00' and e.end_time is None
    assert 'Bratislava' in e.address
    assert extract_source_html(html,'https://a4.sk/news/2027/10/24/story')==[]
    assert extract_source_html(html.replace('sobota o 19:00','sobota'),url)==[]


def test_bkis_explicit_fields_not_premiere_or_footer():
    html='''<h1>Generácia Z</h1><p><strong>Začiatok:</strong> 21. 10. 2027 | 11:00 hod</p>
    <p><strong>Miesto:</strong> DPOH</p><p><strong>Adresa:</strong> Laurinská 20, Bratislava</p>
    <p><strong>Organizátor:</strong> DPOH</p><p>Premiéra 13.9.2024</p>'''
    e=normalize_event(extract_source_html(html,'https://www.bkis.sk/udalost/generacia-z/id/49/')[0])
    assert e.start_time=='2027-10-21T11:00:00+02:00' and e.end_time is None
    assert e.organizer_name=='DPOH'
    assert extract_source_html(html,'https://www.bkis.sk/blog/news/')==[]


def test_sng_explicit_exhibition_range_not_biography():
    html='<h1>Network</h1><p>Born 1956. Exhibited 2023.</p><div class="whitespace-nowrap"> (29/5/2027 - 25/10/2027) </div>'
    e=normalize_event(extract_source_html(html,'https://www.sng.sk/en/slovak-national-gallery/events/network')[0])
    assert e.start_time.startswith('2027-05-29') and e.end_time is None and e.end_date=='2027-10-25'
    assert extract_source_html(html,'https://sng.sk/en/zvolen-castle/events/network')==[]


def test_distinct_endpoints_share_host_controls_and_survive_restart(tmp_path):
    path=str(tmp_path/'state.db');s=State(path)
    for i in range(20):s.discover(f'https://hall.example/events/{i}','https://city.example/events')
    s.discover('https://hall.example/events/0?utm_source=x','https://city.example/events')
    assert s.db.execute('SELECT count(*) FROM candidates').fetchone()[0]==1
    assert s.db.execute('SELECT count(*) FROM candidate_endpoints').fetchone()[0]==8
    assert len(s.inspection_urls('hall.example'))==4
    original=s.inspection_urls('hall.example');s.candidate_result('hall.example',{'inspection/urls':original},True)
    assert s.inspection_urls('hall.example')!=original
    s.close();s=State(path)
    assert s.db.execute('SELECT count(*) FROM candidate_endpoints').fetchone()[0]==8
    s.close()


def test_unchanged_observation_does_not_reset_delivery_backoff(tmp_path):
    s=State(str(tmp_path/'state.db'));payload={'source_url':'https://hall.example/event','title':'Concert','start_time':'2027-01-02'}
    s.enqueue(payload)
    with s.db:s.db.execute("UPDATE outbox SET next_try=12345,attempts=3,error='offline'")
    s.enqueue(payload);r=s.db.execute('SELECT * FROM outbox').fetchone()
    assert r['next_try']==12345 and r['attempts']==3
    s.enqueue({**payload,'description':'Corrected venue evidence'});r=s.db.execute('SELECT * FROM outbox').fetchone()
    assert r['next_try']==0 and r['attempts']==0 and r['error'] is None
    s.close()


def test_temporary_candidate_failure_cannot_promote_to_trusted(tmp_path):
    s=State(str(tmp_path/'state.db'));s.discover('https://hall.example/events','https://city.example/events')
    stats={'quality/events':5,'quality/score_total':400}
    s.candidate_result('hall.example',stats,True)
    s.candidate_result('hall.example',stats,False)
    row=s.db.execute('SELECT * FROM candidates').fetchone()
    assert row['status']=='probation' and row['good_runs']==0 and row['reason']=='temporary_failure'
    s.close()


def test_unsupported_extraction_is_distinguished(tmp_path):
    s=State(str(tmp_path/'state.db'));s.discover('https://hall.example/events','https://city.example/events')
    s.candidate_result('hall.example',{'extraction/unsupported_pages':3},True)
    assert s.db.execute('SELECT reason FROM candidates').fetchone()[0]=='unsupported_extraction'
    s.close()


def test_scrapy_current_hooks_allow_omitted_spider():
    from crawler.pipelines import NormalizePipeline
    from crawler.items import RawEvent
    crawler=SimpleNamespace(spider=SimpleNamespace(crawler=SimpleNamespace(stats=Mock())))
    p=NormalizePipeline.from_crawler(crawler)
    assert p.process_item(RawEvent(title='Concert',start_raw='2027-01-02',source_url='https://hall.example')).title=='Concert'


def test_goout_real_relational_feeder_keeps_occurrences_and_locality():
    from crawler.extraction.goout_extractor import extract_goout_events
    data={'events':{'7':{'id':7,'name':'Jazz','text':'A concert','category':{'name':'Concerts'}}},
          'venues':{'9':{'name':'Hall','address':'Street 1','city':'Bratislava','latitude':48.15,'longitude':17.12}},
          'schedule':[
              {'id':1,'eventId':7,'venueId':9,'venueLocality':{'enum':'SK_BRATISLAVA'},'url':'/en/jazz/show1/',
               'startISO8601':'2027-01-02T19:00:00+01:00','endISO8601':'2027-01-02T20:30:00+01:00'},
              {'id':2,'eventId':7,'venueId':9,'venueLocality':{'enum':'SK_BRATISLAVA'},'url':'/en/jazz/show2/',
               'startISO8601':'2027-01-02T22:00:00+01:00','cancelled':True},
              {'id':3,'eventId':7,'venueId':9,'venueLocality':{'name':'Prague'},'url':'/en/jazz/prague/',
               'startISO8601':'2027-01-02T22:00:00+01:00'}]}
    raw=extract_goout_events(data,'https://goout.net/services/feeder/v1/events.json')
    assert len(raw)==2 and len({e.start_raw for e in raw})==2
    assert raw[0].venue_name=='Hall' and raw[0].latitude==48.15
    assert raw[0].source_url=='https://goout.net/en/jazz/show1/' and raw[1].event_status=='cancelled'
    assert normalize_event(raw[0]).end_time=='2027-01-02T20:30:00+01:00'
    data['schedule'][0]['endISO8601']='2038-01-01T23:59:00+01:00'
    assert extract_goout_events(data,'https://goout.net/events')[0].end_raw is None


def test_feeder_pagination_monotonic_and_bounded():
    from scrapy.http import TextResponse
    seed=next(s for s in ACTIVE_SOURCES if s.domain=='goout.net')
    spider=DiscoverySpider(source=seed);spider.crawler=SimpleNamespace(stats=Mock())
    url='https://goout.net/services/feeder/v1/events.json?locality=30'
    def response(page):
        return TextResponse(url,body=b'{"hasNext":true,"schedule":[],"events":{}}',encoding='utf-8',
            request=Request(url,meta={'source':seed,'feeder_page':page}))
    assert list(spider.parse_goout(response(1)))[0].url.endswith('page=2')
    assert list(spider.parse_goout(response(5)))==[]
    spider.crawler.stats.inc_value.assert_any_call('resource/page_limit')


def test_calendar_endpoint_displaces_detail_saturation_not_host_trust(tmp_path):
    s=State(str(tmp_path/'state.db'))
    for i in range(8):s.discover(f'https://hall.example/event/{i}','https://city.example/events')
    s.discover('https://hall.example/events.ics','https://city.example/events')
    assert s.inspection_urls('hall.example')[0]=='https://hall.example/events.ics'
    s.discover('https://hall.example/events.ics','https://city.example/events')
    assert s.db.execute('SELECT evidence_count FROM candidates').fetchone()[0]==9
    assert s.db.execute('SELECT count(*) FROM candidate_endpoints').fetchone()[0]==8
    s.close();s=State(str(tmp_path/'state.db'))
    assert s.db.execute('SELECT count(*) FROM candidate_endpoints').fetchone()[0]==8
    s.close()


def test_registered_failure_backoff_does_not_wait_full_six_hour_interval(tmp_path):
    s=State(str(tmp_path/'state.db'));seed=ACTIVE_SOURCES[0];s.seed(seed)
    now=time.time()
    s.finish(s.begin(seed.domain),seed,False,{})
    next_run=s.db.execute('SELECT next_run FROM sources').fetchone()[0]
    assert 299<=next_run-now<=302
    for _ in range(8):s.finish(s.begin(seed.domain),seed,False,{})
    assert s.db.execute('SELECT next_run FROM sources').fetchone()[0]-time.time()<=3601
    s.close()


def test_audit_acceptance_never_claims_durable_enqueue():
    from crawler.pipelines import QualityAuditPipeline
    from crawler.items import RawEvent
    stats=Mock();stats.get_value.return_value=0
    spider=SimpleNamespace(sources=[],crawler=SimpleNamespace(stats=stats))
    event=normalize_event(RawEvent(title='Concert',start_raw='2027-01-02T19:00:00Z',source_url='https://hall.example/events'))
    QualityAuditPipeline().process_item(event,spider)
    assert not any(call.args[0]=='ingestion/queued' for call in stats.inc_value.call_args_list)


def test_once_uses_finite_source_snapshot_and_interleaves_candidates(tmp_path,monkeypatch):
    import sys
    import threading
    from crawler import worker
    monkeypatch.setenv('CRAWLER_STATE_PATH',str(tmp_path/'state.db'))
    monkeypatch.setenv('INGESTION_API_KEY','test-key')
    monkeypatch.setattr(sys,'argv',['worker','--once'])
    monkeypatch.setattr(worker.signal,'signal',Mock())
    monkeypatch.setattr(worker,'stop',threading.Event())
    monkeypatch.setattr(worker,'sync_runtime_config',Mock())
    monkeypatch.setattr(worker,'deliver',Mock())
    monkeypatch.setattr(worker.requests,'post',Mock(return_value=Mock(raise_for_status=lambda:None)))
    order=[]
    # Keep sources due to model short backoff expiring during slow later jobs.
    monkeypatch.setattr(worker,'run_source',lambda state,seed,*a,**kw:order.append(seed.domain))
    monkeypatch.setattr(worker,'discovery_cycle',lambda *a,**kw:order.append('candidate'))
    worker.main()
    assert order[0]=='candidate'
    assert order[1::2]==[s.domain for s in ACTIVE_SOURCES]
    assert order[2::2]==['candidate']*len(ACTIVE_SOURCES)


def test_add_to_calendar_actions_are_not_sources_but_public_ics_can_be():
    from crawler.spiders.discovery import allowed_url
    assert not allowed_url('https://www.google.com/calendar/event?action=TEMPLATE&text=Concert')
    assert allowed_url('https://calendar.google.com/calendar/ical/public-calendar/public/basic.ics')


def test_visit_date_metadata_preserves_inclusive_date_without_fake_end_clock():
    from crawler.extraction.visit_extractor import extract_visit_events
    from crawler.processing.validate import validate_event
    from datetime import datetime,timedelta,timezone
    end=(datetime.now(timezone.utc)+timedelta(days=3)).date().isoformat()
    html=f'''<h1 class="title">Exhibition</h1><div class="event-date">
    <span class="start-date" content="2026-01-02T00:00:00+00:00"></span>
    <span class="end-date" content="{end}T00:00:00+00:00"></span></div>
    <li class="address"><span class="value">Gallery</span></li>'''
    event=normalize_event(extract_visit_events(html,'https://www.visitbratislava.com/events/exhibition/')[0])
    assert event.end_time is None and event.end_date==end
    assert event.temporal_evidence=='date_range' and validate_event(event).accepted


def test_cancellations_are_valid_updates_but_not_productive_future_yield(tmp_path):
    from crawler.items import RawEvent
    from crawler.processing.validate import validate_event
    e=normalize_event(RawEvent(title='Concert',start_raw='2020-01-02T20:00:00Z',
        source_url='https://hall.example/event',venue_name='Hall',event_status='cancelled',extraction_confidence=.95))
    assert validate_event(e).accepted
    s=State(str(tmp_path/'state.db'));s.discover('https://hall.example/events','https://city.example/events')
    for _ in range(3):s.candidate_result('hall.example',{'quality/events':5,'quality/score_total':400,'quality/future_events':0},True)
    assert s.db.execute('SELECT status FROM candidates').fetchone()[0]!='trusted'
    s.close()


def test_consistent_backup_keeps_schedule_candidates_and_outbox(tmp_path):
    import sqlite3
    from crawler.backup import backup
    path=tmp_path/'state.db';s=State(str(path));seed=ACTIVE_SOURCES[0];s.seed(seed)
    s.finish(s.begin(seed.domain),seed,False,{})
    s.discover('https://hall.example/events','https://city.example/events')
    s.enqueue({'source_url':'https://hall.example/event','title':'Concert','start_time':'2027-01-02'})
    output=tmp_path/'backup.sqlite'
    assert backup(path,output)['integrity']=='ok'
    with sqlite3.connect(output) as restored:
        assert restored.execute('SELECT count(*) FROM outbox').fetchone()[0]==1
        assert restored.execute('SELECT failures FROM sources').fetchone()[0]==1
        assert restored.execute('SELECT count(*) FROM candidate_endpoints').fetchone()[0]==1
    with pytest.raises(ValueError):backup(path,output)
    s.close()


def test_retry_after_date_and_scheduler_deferral_survive_restart(tmp_path,monkeypatch):
    from email.utils import format_datetime
    from datetime import datetime,timedelta,timezone
    from crawler.retry import retry_after
    date=format_datetime(datetime.now(timezone.utc)+timedelta(hours=3))
    assert 10798<retry_after(date)<=10800
    assert retry_after('NaN')==60 and retry_after('120')==120
    path=str(tmp_path/'state.db');s=State(path);seed=ACTIVE_SOURCES[0];s.seed(seed)
    until=time.time()+10800;s.finish(s.begin(seed.domain),seed,False,{'source/retry_after_until':until})
    s.close();s=State(path)
    assert s.db.execute('SELECT next_run FROM sources').fetchone()[0]>=until
    s.close()


def test_pipeline_enqueue_error_is_a_failed_run():
    from crawler.run import successful
    # Scrapy reports item processing failures separately from callback failures.
    assert not successful({'finish_reason':'finished','response_received_count':2,'item_error_count':1},[])


def test_pipeline_errors_are_wired_to_run_failure():
    from scrapy import signals
    from scrapy.signalmanager import SignalManager
    from twisted.python.failure import Failure
    from crawler.run import track_pipeline_errors
    stats=Mock();errors=[]
    crawler=SimpleNamespace(stats=stats,signals=SignalManager())
    track_pipeline_errors(crawler,errors)
    crawler.signals.send_catch_log(signals.item_error,failure=Failure(RuntimeError('Storage unavailable')))
    stats.inc_value.assert_called_once_with('item_error_count')
    assert errors==['item_pipeline_failure:RuntimeError']


def test_geocoder_retry_after_cools_down_all_queries_across_restart(tmp_path,monkeypatch):
    import requests
    from crawler.pipelines import GeocodePipeline
    monkeypatch.setenv('CRAWLER_STATE_PATH',str(tmp_path/'geo.db'))
    spider=SimpleNamespace(settings={'GEOCODER_URL':'https://geo.example/search','GEOCODER_USER_AGENT':'Test'})
    response=requests.Response();response.status_code=429;response.headers['Retry-After']='300'
    get=Mock(return_value=response);monkeypatch.setattr(requests,'get',get)
    def event(name):return SimpleNamespace(venue_name=name,address=name+', Bratislava',latitude=None,longitude=None)
    p=GeocodePipeline();p.open_spider(spider);p.process_item(event('Hall One'),spider);p.process_item(event('Hall Two'),spider);p.close_spider(spider)
    p=GeocodePipeline();p.open_spider(spider);p.process_item(event('Hall Three'),spider);p.close_spider(spider)
    assert get.call_count==1


def test_ics_date_only_exclusive_end_becomes_inclusive_date_without_clock():
    from crawler.extraction.feeds import extract_feed
    text='BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Exhibition\nDTSTART;VALUE=DATE:20270102\nDTEND;VALUE=DATE:20270105\nLOCATION:Gallery Bratislava\nEND:VEVENT\nEND:VCALENDAR'
    e=normalize_event(extract_feed(text,'https://hall.example/events.ics')[0])
    assert e.end_time is None and e.end_date=='2027-01-04'


def test_dated_stara_archive_and_binary_page_path_do_not_spend_crawl_budget():
    from crawler.spiders.discovery import allowed_url
    assert navigation_url('https://staratrznica.sk/sk/program/market/2000-01-02','staratrznica.sk') is None
    assert navigation_url('https://staratrznica.sk/sk/program/market/2027-01-02','staratrznica.sk')
    assert not allowed_url('https://hotel.example/uploads/page/13/17.jpeg')


def test_stara_card_has_clean_title_explicit_dated_url_and_clock_range():
    html='<a class="event event-link" href="/sk/program/trh/2027-10-24"><p><strong class="event-date">24. október</strong></p><p><strong>Trh-Piac-Markt 2027</strong><br>9:00 - 15:00</p></a>'
    e=normalize_event(extract_source_html(html,'https://staratrznica.sk/sk/program')[0])
    assert e.title=='Trh-Piac-Markt 2027'
    assert e.start_time=='2027-10-24T09:00:00+02:00' and e.end_time=='2027-10-24T15:00:00+02:00'


def test_dns_cache_pins_public_connections_but_revalidates_redirects_and_expiry(monkeypatch):
    import asyncio,socket
    from crawler import middleware
    from scrapy.exceptions import IgnoreRequest
    async def resolved(value):return value
    monkeypatch.setattr(middleware,'deferToThread',lambda f:f())
    monkeypatch.setattr(middleware,'maybe_deferred_to_future',resolved)
    lookup=Mock(return_value=[(socket.AF_INET,1,6,'',('93.184.216.34',80))])
    monkeypatch.setattr(middleware.socket,'getaddrinfo',lookup)
    guard=middleware.PublicNetworkMiddleware()
    for i in range(100):
        asyncio.run(guard.process_request(Request(f'https://hall.example/events/{i}'),SimpleNamespace()))
    assert lookup.call_count==1 and middleware.dnscache['hall.example']=='93.184.216.34'
    lookup.return_value=[(socket.AF_INET,1,6,'',('127.0.0.1',80))]
    with pytest.raises(IgnoreRequest):
        asyncio.run(guard.process_request(Request('https://hall.example/redirect',meta={'redirect_times':1}),SimpleNamespace()))
    guard.public_addresses['hall.example']=(0,'93.184.216.34')
    with pytest.raises(IgnoreRequest):
        asyncio.run(guard.process_request(Request('https://hall.example/events/new'),SimpleNamespace()))
