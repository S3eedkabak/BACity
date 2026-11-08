"""Independent scheduler time is advanced only in isolated deterministic fixtures."""
import json
from unittest.mock import patch, Mock
from types import SimpleNamespace

from scrapy import Request
from scrapy.http import HtmlResponse

from crawler.sources import SourceSeed
from crawler.state import State
from crawler.qualification import POLICY
from crawler.worker import collect_orphan_run_stats

STATS={'quality/events':2,'quality/unique_events':2,'quality/future_events':2,'quality/unique_future_events':2,
       'quality/score_total':140,'quality/confidence_total':1.8,'validation/rejected':20,
       'validation/rejected/start_date_already_in_the_past':15,'validation/rejected/no_local_evidence':5}


def scheduled(state,stats=STATS,success=True,now=None):
    row=state.db.execute('SELECT * FROM candidates WHERE domain=?',('hall.example',)).fetchone()
    now=now if now is not None else max(row['next_inspection'],100000.)+1
    seed=SourceSeed('Hall','hall.example','https://hall.example','https://hall.example/events','venue',.6,parser='structured')
    with patch('crawler.state.time.time',return_value=now):
        state.seed(seed)
        run=state.begin(seed.domain)
        state.finish(run,seed,success,stats)
        state.candidate_result(seed.domain,stats,success,run_id=run)
    return run


def make(tmp_path):
    state=State(str(tmp_path/'state.db'))
    state.discover('https://hall.example/events','https://city.example/program')
    return state


def test_scratch_gc_preserves_running_jobs_and_durable_evidence(tmp_path):
    state=State(str(tmp_path/'state.db'))
    with state.db:
        finished=state.db.execute("INSERT INTO runs(domain,started,finished,success) VALUES('done.example',1,2,1)").lastrowid
        running=state.db.execute("INSERT INTO runs(domain,started) VALUES('live.example',1)").lastrowid
        state.db.execute("INSERT INTO outbox(key,payload,created) VALUES('pending','{}',1)")
    for run_id in (finished,running,999):
        path=tmp_path/f'run-{run_id}.json';path.write_text('{}')
        import os
        os.utime(path,(1,1))
    assert collect_orphan_run_stats(state,str(tmp_path/'state.db'),now=100000)==1
    assert not (tmp_path/f'run-{finished}.json').exists()
    assert (tmp_path/f'run-{running}.json').exists()
    assert (tmp_path/'run-999.json').exists()
    assert state.db.execute('SELECT count(*) FROM runs').fetchone()[0]==2
    assert state.db.execute('SELECT count(*) FROM outbox').fetchone()[0]==1
    state.close()


def test_imperfect_source_independent_trust_replay_restart_and_degrade(tmp_path):
    state=make(tmp_path)
    run=scheduled(state)
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]=='probation'
    state.candidate_result('hall.example',STATS,True,run_id=run)
    assert state.db.execute('SELECT good_runs FROM candidates').fetchone()[0]==1
    state.close();state=State(str(tmp_path/'state.db'))
    scheduled(state)
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]=='trusted'
    for _ in range(POLICY.degradation_runs): scheduled(state,{},False)
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]=='degraded'
    scheduled(state);scheduled(state)
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]=='trusted'
    assert state.db.execute('SELECT count(*) FROM qualification_runs').fetchone()[0]==7
    state.close()


def test_retry_audit_zero_cancelled_and_low_volume(tmp_path):
    state=make(tmp_path)
    stats={**STATS,'quality/events':1,'quality/unique_events':1,'quality/unique_future_events':1,
           'quality/score_total':70,'quality/confidence_total':.9}
    first=scheduled(state,stats)
    started=state.db.execute('SELECT started FROM runs WHERE id=?',(first,)).fetchone()[0]
    scheduled(state,stats,now=started+1)
    assert state.db.execute('SELECT good_runs FROM candidates').fetchone()[0]==1
    scheduled(state,{**stats,'audit':True})
    assert state.db.execute('SELECT good_runs FROM candidates').fetchone()[0]==1
    scheduled(state,{**stats,'quality/unique_future_events':0})
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]!='trusted'
    scheduled(state,stats);scheduled(state,stats)
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]=='trusted'
    state.close()


def test_no_raw_yield_or_http_success_promotion(tmp_path):
    state=make(tmp_path)
    for _ in range(5): scheduled(state,{'downloader/response_status_count/200':1})
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]=='inspected'
    # Serious malformed dates do count against extraction integrity.
    for _ in range(3): scheduled(state,{**STATS,'validation/rejected/normalization':20,
        'validation/rejected/start_date_already_in_the_past':0,'validation/rejected/no_local_evidence':0})
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]!='trusted'
    state.close()


def test_controlled_graph_and_loop_bounds(tmp_path,monkeypatch):
    monkeypatch.setenv('CRAWLER_STATE_PATH',str(tmp_path/'state.db'))
    state=make(tmp_path);scheduled(state)
    assert state.discover('https://partner.example/program','https://hall.example/events/music')
    assert not state.discover('https://third.example/program','https://partner.example/program')
    with state.db: state.db.execute("UPDATE candidates SET status='probation' WHERE domain='partner.example'")
    assert not state.discover('https://third.example/program','https://partner.example/program')
    assert not state.discover('https://hall.example/events','https://partner.example/program')
    assert state.db.execute("SELECT graph_depth FROM candidates WHERE domain='partner.example'").fetchone()[0]==2
    state.close()
    from crawler.spiders.discovery import DiscoverySpider
    seed=SourceSeed('Hall','hall.example','https://hall.example','https://hall.example/events','venue',.6,parser='structured')
    spider=DiscoverySpider(source=seed);spider.crawler=SimpleNamespace(stats=Mock())
    html='<script type="application/ld+json">{"@type":"Event","name":"Music","startDate":"2027-01-02T20:00:00Z"}</script><a href="https://feed.example/program">Venue calendar</a><a href="https://random.example/events">Advertisements</a>'
    request=Request('https://hall.example/events/music',meta={'source':seed})
    list(spider.parse(HtmlResponse(request.url,body=html.encode(),encoding='utf-8',request=request)))
    assert spider.state.db.execute("SELECT 1 FROM candidates WHERE domain='feed.example'").fetchone()
    assert not spider.state.db.execute("SELECT 1 FROM candidates WHERE domain='random.example'").fetchone()
    spider.closed('finished')


def test_duplicate_urls_cannot_inflate_occurrence_evidence():
    from datetime import datetime,timedelta,timezone
    from crawler.pipelines import QualityAuditPipeline
    from crawler.items import RawEvent
    from crawler.processing.normalize import normalize_event
    values={}
    class Stats:
        def get_value(self,key,default=0):return values.get(key,default)
        def inc_value(self,key,count=1):values[key]=values.get(key,0)+count
    spider=SimpleNamespace(sources=[],crawler=SimpleNamespace(stats=Stats()))
    pipeline=QualityAuditPipeline()
    start=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    for url in ('https://hall.example/events/one','https://hall.example/events/copy'):
        event=normalize_event(RawEvent(title='Public Concert',start_raw=start,source_url=url,
            venue_name='Hall',address='Public Street, Bratislava',extraction_confidence=.9))
        pipeline.process_item(event,spider)
    assert values['quality/events']==2
    assert values['quality/unique_events']==values['quality/unique_future_events']==1


def test_legacy_scheduler_migration_retains_candidates_endpoints_and_history(tmp_path):
    import sqlite3
    state=make(tmp_path)
    state.db.execute("UPDATE candidates SET attempts=7,status='probation',reason='low_valid_yield'")
    state.db.commit();state.close()
    with sqlite3.connect(tmp_path/'state.db') as db:
        db.execute('ALTER TABLE candidates RENAME TO original_candidates')
        db.execute("""CREATE TABLE candidates (
          domain TEXT PRIMARY KEY,url TEXT NOT NULL,origin TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'discovered',
          discovered REAL NOT NULL,inspected REAL,next_inspection REAL NOT NULL DEFAULT 0,evidence_count INTEGER NOT NULL DEFAULT 1,
          attempts INTEGER NOT NULL DEFAULT 0,good_runs INTEGER NOT NULL DEFAULT 0,failures INTEGER NOT NULL DEFAULT 0,
          reason TEXT,metrics TEXT NOT NULL DEFAULT '{}',
          CHECK(status IN ('discovered','inspected','probation','trusted','rejected','blocked','disabled')))""")
        db.execute('INSERT INTO candidates SELECT domain,url,origin,status,discovered,inspected,next_inspection,evidence_count,attempts,good_runs,failures,reason,metrics FROM original_candidates')
        db.execute('DROP TABLE original_candidates')
    state=State(str(tmp_path/'state.db'))
    row=state.db.execute('SELECT * FROM candidates').fetchone()
    assert row['attempts']==7 and row['status']=='probation' and row['reason']=='low_valid_yield'
    assert row['last_qualified'] is None
    assert state.db.execute('SELECT count(*) FROM candidate_endpoints').fetchone()[0]==1
    with state.db: state.db.execute("UPDATE candidates SET status='degraded'")
    state.close()


def test_worker_finish_persists_run_and_qualification_together(tmp_path):
    state=make(tmp_path)
    seed=SourceSeed('Hall','hall.example','https://hall.example','https://hall.example/events','venue',.6,parser='structured')
    state.seed(seed);run=state.begin(seed.domain)
    state.finish(run,seed,True,STATS,inspection=True)
    state.close();state=State(str(tmp_path/'state.db'))
    assert state.db.execute('SELECT success FROM runs WHERE id=?',(run,)).fetchone()[0]==1
    assert state.db.execute('SELECT count(*) FROM qualification_runs WHERE run_id=?',(run,)).fetchone()[0]==1
    assert state.db.execute('SELECT good_runs FROM candidates').fetchone()[0]==1
    state.candidate_result(seed.domain,STATS,True,run_id=run)
    assert state.db.execute('SELECT good_runs FROM candidates').fetchone()[0]==1
    state.close()


def test_structured_organizer_provenance_expands_only_bounded_public_hosts(tmp_path,monkeypatch):
    monkeypatch.setenv('CRAWLER_STATE_PATH',str(tmp_path/'state.db'))
    state=make(tmp_path);scheduled(state);state.close()
    from crawler.spiders.discovery import DiscoverySpider
    seed=SourceSeed('Hall','hall.example','https://hall.example','https://hall.example/events','venue',.6,parser='structured')
    spider=DiscoverySpider(source=seed);spider.crawler=SimpleNamespace(stats=Mock())
    data={'@type':'Event','name':'Public Concert','startDate':'2027-01-02T20:00:00Z',
          'location':{'name':'Public Hall','address':'Public Street, Bratislava','url':'https://venue-calendar.example/'},
          'organizer':{'name':'Official Organizer','url':'https://organizer.example/'},'sameAs':'https://advertising.example/'}
    request=Request('https://hall.example/events/music',meta={'source':seed})
    list(spider.parse(HtmlResponse(request.url,body=('<script type="application/ld+json">'+json.dumps(data)+'</script>').encode(),encoding='utf-8',request=request)))
    rows=spider.state.db.execute("SELECT domain,graph_depth FROM candidates WHERE domain!='hall.example'").fetchall()
    assert {row['domain'] for row in rows}=={'organizer.example','venue-calendar.example'}
    assert all(row['graph_depth']==2 for row in rows)
    evidence=spider.state.db.execute("SELECT origin,origin_verified FROM candidate_endpoints WHERE domain='organizer.example'").fetchone()
    assert evidence['origin']==request.url and evidence['origin_verified']==1
    spider.closed('finished')


def test_new_link_volume_does_not_jump_a_due_productive_venue(tmp_path):
    with patch('crawler.state.time.time',return_value=100000):state=make(tmp_path)
    scheduled(state,now=100001)
    with patch('crawler.state.time.time',return_value=103602):
        for index in range(20):state.discover(f'https://new{index}.example/calendar','https://city.example/events')
        assert state.inspect_due()[0]['domain']=='hall.example'
    state.close()


def test_realistic_ticket_calendar_missing_optional_fields_can_qualify(tmp_path):
    state=make(tmp_path)
    stats={'quality/events':9,'quality/unique_events':9,'quality/unique_future_events':9,
        'quality/score_total':465,'quality/confidence_total':7.65,'validation/rejected':3,
        'validation/rejected/no_local_evidence':2,'validation/rejected/start_date_already_in_the_past':1}
    scheduled(state,stats);scheduled(state,stats)
    assert state.db.execute('SELECT status FROM candidates').fetchone()[0]=='trusted'
    state.close()
