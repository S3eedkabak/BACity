"""Product workflow regressions; all source/provider content is synthetic."""
import time
import uuid
import json
import pytest
from fastapi import HTTPException
from app.social.config import settings
from app.social.models import Publisher, CollectionJob, Observation, AuditEvent, Control, StaffSession
from app.social.security import digest
from app.social.workflows import available, schedule, stage
from app.social.acquisition.apify import actor_input
from app.social.acquisition.scrapingant import collect
from .test_scrapingant import document


def enable(monkeypatch):
    monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','true')
    monkeypatch.setenv('APIFY_ENABLED','true')
    monkeypatch.setenv('APIFY_TOKEN_CONFIGURED','true')
    monkeypatch.setenv('INSTAGRAM_ACQUISITION_PROVIDER','apify')
    settings.cache_clear()


def proposal(client):
    result=client.post('/api/publishers',json={'url':'@simple_fixture','name':'Simple fixture venue',
        'relevance':'Concerts and performances in Bratislava','venue_name':'Fixture venue','address':'Fixture street 1'})
    assert result.status_code==201,result.text
    return result.json()


def approve(client,p):
    return client.post('/api/publishers/'+p['id']+'/approve-and-start',
        json={'confirmed':True,'reviewed_updated':p['updated']})


def test_add_review_approve_starts_without_extra_access_steps(social,monkeypatch):
    enable(monkeypatch)
    owner,staff,_,_=social.login(verified_age=1800)
    p=proposal(owner)
    assert p['approval']=='pending' and not p['enabled'] and p['posts_per_profile']==2
    with social.factory() as db:assert schedule(db)==[]
    response=approve(owner,p);assert response.status_code==200,response.text
    p=response.json()
    assert p['enabled'] and p['approval']=='approved' and p['collection_approved']
    assert p['posts_per_profile']==2 and p['interval_seconds']==86400 and p['priority']==50
    assert p['method']=='apify' and p['approved_by']==staff.id and p['permission_expires'] is None
    with social.factory() as db:
        assert available(db.get(Publisher,p['id']))
        assert len(schedule(db,provider_filter='apify'))==1
        assert schedule(db,provider_filter='apify')==[]
        assert db.query(AuditEvent).filter_by().count()>0
        from app.models.event import Event
        assert db.query(Event).count()==0


@pytest.mark.parametrize('role',['SOCIAL_EDITOR','SOCIAL_REVIEWER','SOCIAL_VIEWER'])
def test_non_approvers_cannot_activate_source(social,monkeypatch,role):
    enable(monkeypatch);owner,_,_,_=social.login();p=proposal(owner)
    client,_,_,_=social.login(role)
    assert approve(client,p).status_code==403
    with social.factory() as db:assert not db.get(Publisher,p['id']).enabled


@pytest.mark.parametrize('condition',['changed','unconfirmed','disabled','stop','restricted','capacity'])
def test_review_must_be_current_and_activation_failure_is_atomic(social,monkeypatch,condition):
    enable(monkeypatch);owner,staff,_,_=social.login();p=proposal(owner)
    if condition=='disabled':monkeypatch.setenv('APIFY_ENABLED','false')
    with social.factory() as db:
        row=db.get(Publisher,p['id'])
        if condition=='changed':row.updated+=1
        if condition=='restricted':row.eligibility='blocked'
        if condition=='stop':db.add(Control(id=1,emergency_stop=True))
        db.commit()
    if condition=='capacity':
        monkeypatch.setenv('APIFY_MAX_ACTIVE_PROFILES','1')
        social.publisher(staff,method='apify')
    body={'confirmed':condition!='unconfirmed','reviewed_updated':p['updated']}
    result=owner.post('/api/publishers/'+p['id']+'/approve-and-start',json=body)
    assert result.status_code in (409,422),result.text
    with social.factory() as db:
        row=db.get(Publisher,p['id']);assert row.approval=='pending' and not row.enabled and not row.collection_approved


def test_edit_revokes_approval_and_pause_resume_cannot_repeat_daily_check(social,monkeypatch):
    enable(monkeypatch);owner,_,_,_=social.login();p=proposal(owner)
    p=approve(owner,p).json()
    with social.factory() as db:
        row=db.get(Publisher,p['id']);row.last_attempt=time.time();row.last_success=time.time();row.next_due=0;db.commit()
    assert owner.post('/api/publishers/'+p['id']+'/monitoring',json={'enabled':False}).status_code==200
    p=owner.get('/api/publishers/'+p['id']).json()['publisher'];p=approve(owner,p).json()
    assert p['next_due']>=p['last_attempt']+86400
    assert owner.post('/api/publishers/'+p['id']+'/retry').status_code==409
    with social.factory() as db:
        row=db.get(Publisher,p['id']);row.next_due=0;db.commit();assert schedule(db,provider_filter='apify')==[]
    edit=owner.patch('/api/publishers/'+p['id'],json={'url':p['url'],'name':'Updated fixture','relevance':'Updated Bratislava venue details'})
    assert edit.status_code==200
    assert not edit.json()['enabled'] and not edit.json()['collection_approved'] and edit.json()['approval']=='pending'


def test_stage_rejects_third_post_across_deliveries(social,announcement):
    _,staff,_,_=social.login();p=social.publisher(staff)
    with social.factory() as db:
        p=db.get(Publisher,p.id);job=CollectionJob(publisher_id=p.id,dedup_key=uuid.uuid4().hex);db.add(job);db.flush()
        for i in range(2):
            content=announcement|{'external_id':'Bounded'+str(i),'source_url':'https://www.instagram.com/p/Bounded'+str(i)+'/'}
            assert stage(db,p,content,'test',job=job)[1]
        # Duplicate acknowledgement is still legal at the bound.
        assert not stage(db,p,content,'test',job=job)[1]
        with pytest.raises(HTTPException,match='two posts'):
            stage(db,p,announcement|{'external_id':'ThirdPost','source_url':'https://www.instagram.com/p/ThirdPost/'},'test',job=job)
        assert db.query(Observation).filter_by(job_id=job.id).count()==2


def test_scrapingant_never_returns_more_than_two_posts():
    doc=document();html=doc['html'];start=html.index('<script type="application/json">')+len('<script type="application/json">');end=html.index('</script>')
    data=json.loads(html[start:end]);edges=data['data']['user']['edge_owner_to_timeline_media']['edges']
    edges.extend([{'node':edges[0]['node']|{'shortcode':'Extra'+str(i),'taken_at_timestamp':int(time.time()-i)}} for i in range(5)])
    doc['html']=html[:start]+json.dumps(data)+html[end:]
    class Client:
        bytes=100
        def request(self,kind,url):return doc,1
    calls=[]
    def quota(action,payload):
        calls.append(action)
        if action=='status':return {'needs_sync':False,'suspension_reason':None}
        if action=='settle':return {'cost':1,'cost_kind':'reported'}
        return {}
    result=collect({'url':'https://www.instagram.com/fixture_venue/'},Client(),quota)
    assert result['outcome']=='success' and len(result['observations'])==2
    assert calls.count('reserve')==1 # No extra post-page calls when two captions already exist.


def test_actor_request_cannot_exceed_two_results():
    assert actor_input([{'url':'https://www.instagram.com/fixture_venue/','checkpoint_timestamp':None}],50)['resultsLimit']==2


def test_staff_can_work_past_fifteen_minutes_but_expiry_and_revocation_remain(social):
    owner,staff,_,raw=social.login(age=1800,verified_age=1800)
    assert owner.get('/api/dashboard').status_code==200
    # Critical team/passkey changes still require fresh identity verification.
    assert owner.post('/api/staff',json={'email':'new@test.invalid','name':'New person','role':'SOCIAL_EDITOR'}).status_code in (403,422)
    with social.factory() as db:
        session=db.get(StaffSession,digest(raw));session.revoked=True;db.commit()
    assert owner.get('/api/dashboard').status_code==401

@pytest.mark.skipif(not __import__('os').getenv('TEST_POSTGRES_URL'),reason='Disposable PostgreSQL not configured')
def test_upgrade_clamps_existing_limit_without_starting_publishers():
    import os,subprocess,sys
    from pathlib import Path
    from sqlalchemy import create_engine,text
    from sqlalchemy.engine import make_url
    url=make_url(os.environ['TEST_POSTGRES_URL']);name='panel_upgrade_'+uuid.uuid4().hex
    admin=create_engine(url,isolation_level='AUTOCOMMIT')
    with admin.connect() as db:db.execute(text('CREATE DATABASE '+name))
    target=url.set(database=name);engine=create_engine(target)
    env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
    api=Path(__file__).resolve().parents[2]
    def migrate(version):
        r=subprocess.run([sys.executable,'-m','alembic','upgrade',version],cwd=api,env=env,capture_output=True,text=True)
        assert r.returncode==0,r.stderr
    try:
        migrate('0027')
        with engine.begin() as db:
            db.execute(text("INSERT INTO l4_staff(id,email,name,role,active,version,created) VALUES('staff','fixture@example.org','Fixture','OWNER',true,1,0)"))
            db.execute(text("""INSERT INTO l4_publishers(id,platform,url,external_id,target_type,name,publisher_type,relevance,approval,eligibility,method,priority,interval_seconds,enabled,next_due,failures,discovered_by,created_by,created,updated,posts_per_profile)
                VALUES('publisher','instagram','https://www.instagram.com/upgrade_fixture/','upgrade_fixture','profile','Fixture','venue','Synthetic upgrade venue','approved','authorization_required','submission',50,86400,false,0,0,'staff_url','staff',0,0,3)"""))
        migrate('head')
        with engine.connect() as db:
            p=db.execute(text('SELECT approval,enabled,collection_approved,posts_per_profile FROM l4_publishers')).one()
            assert p.approval=='approved' and not p.enabled and not p.collection_approved and p.posts_per_profile==2
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0028'
    finally:
        engine.dispose()
        with admin.connect() as db:db.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
        admin.dispose()
