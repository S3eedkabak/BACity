import time
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock
import pytest
from app.social.acquisition.urls import normalize_target
from app.social.config import settings
from app.social.models import Publisher,Observation,EventCandidate,AuditEvent,Staff,CollectionJob
from app.social.security import verify_audit,digest
from app.social.workflows import stage,schedule
from app.social.extraction import extract,content_hash

@pytest.mark.parametrize('raw,expected',[
 ('https://WWW.INSTAGRAM.COM/Venue.Name/?utm_source=site','https://www.instagram.com/venue.name/'),
 ('https://instagram.com/p/Post_A1/','https://www.instagram.com/p/Post_A1/'),
 ('https://www.facebook.com/events/123456789/','https://www.facebook.com/events/123456789/'),
 ('https://www.facebook.com/RealVenue/posts/123456789','https://www.facebook.com/realvenue/posts/123456789/'),
 ('https://www.facebook.com/profile.php?id=123456789','https://www.facebook.com/profile.php?id=123456789'),
 ('https://www.tiktok.com/@Venue/video/1234567890123','https://www.tiktok.com/@venue/video/1234567890123'),
 ('https://novacvernovka.eu/program/example-event','https://novacvernovka.eu/program/example-event'),
])
def test_supported_profile_and_direct_post_identity(raw,expected):
    assert normalize_target(raw).url==expected

@pytest.mark.parametrize('url',[
 'http://instagram.com/venue','https://instagram.com.evil.test/venue','https://user:password@instagram.com/venue',
 'https://instagram.com:444/venue','https://instagram.com/accounts/','https://instagram.com/explore',
 'https://instagram.com/..','https://instagram.com/%2e%2e/','https://instagram.com/venue?access_token=secret',
 'https://instagram.com/venue#secret','https://facebook.com/share/x','https://facebook.com/login',
 'https://tiktok.com/login','https://vm.tiktok.com/short','file:///etc/passwd','https://127.0.0.1/events',
 'https://169.254.169.254/latest/meta-data','https://[::1]/event','https://example.test/anything',
 'https://novacvernovka.eu/program/../../admin','https://novacvernovka.eu//bad',
])
def test_unsafe_or_unsupported_urls_fail_closed(url):
    with pytest.raises(ValueError):
        normalize_target(url)


def test_create_normalize_dedup_no_mass_assignment_or_network(social,monkeypatch):
    client,staff,_,_=social.login('SOCIAL_EDITOR')
    monkeypatch.setattr('socket.getaddrinfo',Mock(side_effect=AssertionError('No network on input')))
    data={'url':'https://instagram.com/GoodVenue/','name':'Good venue','relevance':'Verified venue in Bratislava'}
    result=client.post('/api/publishers',json=data)
    assert result.status_code==201,result.text
    assert result.json()['eligibility']=='authorization_required'
    assert result.json()['approval']=='pending' and not result.json()['enabled']
    assert client.post('/api/publishers',json=data|{'url':'https://www.instagram.com/goodvenue/?utm_source=x'}).status_code==409
    assert client.post('/api/publishers',json=data|{'enabled':True,'approval':'approved'}).status_code==422
    assert client.post('/api/publishers/'+result.json()['id']+'/decision',json={'decision':'approved','note':'I approve this local venue'}).status_code==403
    with social.factory() as db:
        assert db.query(Publisher).count()==1
        assert verify_audit(db.query(AuditEvent).order_by(AuditEvent.sequence))


def test_editorial_approval_does_not_grant_collection_and_suspend_cancels(social,monkeypatch):
    owner,staff,_,_=social.login()
    p=social.publisher(staff,eligibility='authorization_required',permission_basis=None,enabled=False)
    assert owner.post('/api/publishers/'+p.id+'/decision',json={'decision':'approved','note':'Verified local venue identity'}).status_code==200
    assert owner.post('/api/publishers/'+p.id+'/monitoring',json={'enabled':True}).status_code==409
    assert owner.post('/api/publishers/'+p.id+'/access',json={'eligibility':'available','method':'http','permission_basis':'Explicit permission verified in fixture','permission_expires':time.time()+86400}).status_code==200
    assert owner.post('/api/publishers/'+p.id+'/monitoring',json={'enabled':True}).status_code==200
    monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','true');settings.cache_clear()
    with social.factory() as db:
        jobs=schedule(db);assert len(jobs)==1
    assert owner.post('/api/publishers/'+p.id+'/decision',json={'decision':'suspended','note':'Stop all collection immediately'}).status_code==200
    with social.factory() as db:
        assert db.get(CollectionJob,jobs[0]).state=='cancelled'
        assert not db.get(Publisher,p.id).enabled


def test_permitted_evidence_keeps_edited_versions_without_duplicate_event(social,announcement):
    client,staff,_,_=social.login('SOCIAL_EDITOR');p=social.publisher(staff)
    first=client.post('/api/publishers/'+p.id+'/evidence',json=announcement)
    assert first.status_code==201,first.text
    assert first.json()['created']
    assert not client.post('/api/publishers/'+p.id+'/evidence',json=announcement).json()['created']
    edited=announcement|{'caption':announcement['caption']+'\nAdditional public detail'}
    assert client.post('/api/publishers/'+p.id+'/evidence',json=edited).json()['created']
    with social.factory() as db:
        assert db.query(Observation).count()==2
        assert db.query(EventCandidate).count()==1
        assert {o.method for o in db.query(Observation)}=={'user_submission'}
        from app.models.event import Event
        assert db.query(Event).count()==0
    data=client.get('/api/candidates').json()
    assert data['total']==1
    assert data['items'][0]['status']=='qualified'
    assert not data['items'][0]['missing']

@pytest.mark.parametrize('language,word',[('sk','zajtra'),('cs','zitra'),('en','tomorrow')])
def test_relative_dates_use_original_publication_not_collection(social,language,word):
    _,staff,_,_=social.login();p=social.publisher(staff)
    published=datetime(2026,10,24,18,0,tzinfo=timezone.utc)
    caption=f'Koncert Jazz\n{word} 19:00\nFixture Hall Bratislava'
    result=extract(caption,published.isoformat(),p,now=datetime(2026,10,25,12,0,tzinfo=timezone.utc))[0]
    assert result['fields']['event_date']=='2026-10-25'
    assert result['fields']['start_time']=='2026-10-25T18:00:00+00:00'
    assert 'unambiguous_date' in extract(caption,None,p)[0]['missing']


def test_missing_time_dst_expired_non_event_and_multi_event_quarantine(social):
    _,staff,_,_=social.login();p=social.publisher(staff)
    def check(text,now=datetime(2026,1,1,tzinfo=timezone.utc)):
        return extract(text,'2026-01-01T00:00:00+00:00',p,now=now)
    assert check('Koncert\n2026-11-10\nFixture Hall')[0]['fields']['start_time'] is None
    assert 'start_time' in check('Koncert\n2026-11-10\nFixture Hall')[0]['missing']
    assert 'valid_local_time' in check('Koncert\n2026-03-29 02:30\nFixture Hall')[0]['missing']
    assert 'valid_local_time' in check('Koncert\n2026-10-25 02:30\nFixture Hall')[0]['missing']
    assert 'upcoming_date' in check('Koncert\n2025-12-30 20:00\nFixture Hall')[0]['missing']
    assert check('New cocktails\n2026-11-10 20:00\nFixture Hall')==[]
    assert 'schedule_change_review' in check('Koncert cancelled\n2026-11-10 20:00\nFixture Hall')[0]['missing']
    text='Koncert First\n2026-11-10 20:00\nFixture Hall\n\nKoncert Second\n2026-11-11 19:00\nFixture Hall'
    result=check(text)
    assert len(result)==2 and all(not r['missing'] for r in result)
    assert 'unambiguous_date' in check(text.replace('\n\n','\n'))[0]['missing']


def test_review_and_publication_flags_require_independent_authority(social,announcement):
    editor,staff,_,_=social.login('SOCIAL_EDITOR');p=social.publisher(staff)
    editor.post('/api/publishers/'+p.id+'/evidence',json=announcement)
    candidate=editor.get('/api/candidates').json()['items'][0]
    admin,_,_,_=social.login('SOCIAL_ADMIN')
    assert admin.post('/api/candidates/'+candidate['id']+'/review',json={'decision':'approved','note':'Date venue and evidence verified'}).status_code==200
    assert admin.post('/api/candidates/'+candidate['id']+'/publish').status_code==409
    assert editor.post('/api/candidates/'+candidate['id']+'/publish').status_code==403
    with social.factory() as db:
        from app.models.event import Event
        assert db.query(Event).count()==0
        assert db.get(EventCandidate,candidate['id']).status=='approved'


def test_edits_reset_review_and_prevent_self_approval(social,announcement):
    editor,staff,_,_=social.login('SOCIAL_EDITOR');p=social.publisher(staff)
    editor.post('/api/publishers/'+p.id+'/evidence',json=announcement)
    c=editor.get('/api/candidates').json()['items'][0]
    edited={key:c['fields'][key] for key in ('title','start_time','venue_name','address','latitude','longitude')}
    edited['note']='Verified correction against original caption'
    assert editor.patch('/api/candidates/'+c['id'],json=edited).status_code==200
    assert editor.post('/api/candidates/'+c['id']+'/review',json={'decision':'approved','note':'Self approval must be rejected'}).status_code==403
    with social.factory() as db:
        assert db.get(EventCandidate,c['id']).reviewed_hash is None


def test_source_mismatch_and_suspension_cannot_stage(social,announcement):
    editor,staff,_,_=social.login('SOCIAL_EDITOR');p=social.publisher(staff,target_type='post',url=announcement['source_url'],external_id=announcement['external_id'])
    assert editor.post('/api/publishers/'+p.id+'/evidence',json=announcement|{'external_id':'Wrong'}).status_code==422
    assert editor.post('/api/publishers/'+p.id+'/evidence',json=announcement|{'source_url':'https://www.facebook.com/events/123456/','external_id':'123456'}).status_code==422
    with social.factory() as db:
        db.get(Publisher,p.id).approval='suspended';db.commit()
    assert editor.post('/api/publishers/'+p.id+'/evidence',json=announcement).status_code==409


def test_staging_capacity_does_not_break_idempotent_replay(social,announcement,monkeypatch):
    client,staff,_,_=social.login('SOCIAL_EDITOR');p=social.publisher(staff)
    monkeypatch.setenv('SOCIAL_MAX_OBSERVATIONS','1');settings.cache_clear()
    assert client.post('/api/publishers/'+p.id+'/evidence',json=announcement).status_code==201
    assert not client.post('/api/publishers/'+p.id+'/evidence',json=announcement).json()['created']
    assert client.post('/api/publishers/'+p.id+'/evidence',json=announcement|{'caption':announcement['caption']+' edited'}).status_code==409

@pytest.mark.parametrize('date_text,expected',[
 ('November 10, 2030 20:00','2030-11-10T19:00:00+00:00'),
 ('10 November 2030 20:00','2030-11-10T19:00:00+00:00'),
 ('10. listopadu 2030 20:00','2030-11-10T19:00:00+00:00'),
 ('2030-11-10T20:00:00+01:00','2030-11-10T19:00:00+00:00'),
 ('2030-11-10T20:00:00Z','2030-11-10T20:00:00+00:00'),
 ('2030-11-10 20:00 UTC','2030-11-10T20:00:00+00:00'),
])
def test_explicit_english_czech_and_offset_dates_remain_correct(social,date_text,expected):
    _,staff,_,_=social.login();p=social.publisher(staff)
    result=extract('Concert Jazz\n'+date_text+'\nFixture Hall',None,p)[0]
    assert result['fields']['start_time']==expected
    assert not result['missing']
