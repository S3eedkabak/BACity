"""Private poster evidence, safe image decoding, OCR drafts and durable replay."""
import base64,io,json,time,urllib.error,uuid
import pytest
from PIL import Image
from app.social.config import settings
from app.social.models import Observation,PostImage,EventCandidate,Publisher,DeliveryReceipt
from app.social.acquisition.poster import prepare,read_text
from app.social.acquisition.outbox import Outbox
from app.social.acquisition.durable_runner import cycle
from app.social.acquisition.network import fetch,AccessFailure
from app.social.maintenance import prune
from app.social.workflows import stage

def image_bytes():
    out=io.BytesIO();Image.new('RGB',(900,1200),'white').save(out,'PNG');return out.getvalue()

def poster_result(text='HALLOWEEN PARTY\n31.10.2030 20:00\nFixture Hall Bratislava'):
    return prepare(image_bytes(),ocr=lambda image:(text,.96,'ready'))

def source(social,announcement):
    client,staff,_,_=social.login();p=social.publisher(staff,enabled=False)
    with social.factory() as db:
        observation,_=stage(db,db.get(Publisher,p.id),announcement,'test')
        observation.media=['https://scontent.cdninstagram.com/post.jpg'];db.commit();identity=observation.id
    worker=social.client(worker=True);worker.headers['X-Social-Worker-Key']=settings().worker_key
    return client,worker,p,identity

def send_for(worker):
    def send(path,*,payload=None,**kw):
        r=worker.post(path,json=payload or {})
        if r.status_code!=200:raise urllib.error.HTTPError(path,r.status_code,'gateway',{},None)
        return r.json()
    return send

def leased(social,announcement):
    client,worker,p,identity=source(social,announcement);owner='m'*43
    response=worker.post('/media/lease',json={'owner':owner});assert response.status_code==200,response.text
    asset=response.json()['image'];assert asset
    return client,worker,p,identity,owner,asset

def deliver(worker,owner,asset,result,identity=None):
    return worker.post('/outbox/deliver',json={'id':identity or str(uuid.uuid4()),'action':'media:complete','identity':asset['id'],'owner':owner,'payload':result})

def test_private_preview_and_ocr_draft_preserve_caption_and_review(social,announcement):
    client,worker,p,identity,owner,asset=leased(social,announcement)
    with social.factory() as db:
        caption=db.get(Observation,identity).caption
        old=db.query(EventCandidate).filter_by(observation_id=identity).first();old.status='approved';old.reviewed_by=p.created_by;db.commit();old_id=old.id
    result=poster_result();response=deliver(worker,owner,asset,result)
    assert response.status_code==200,response.text
    assert response.json()['new_candidates']==1 and response.json()['public_event_writes']==0
    cached=client.get('/api/post-images/'+asset['id']);assert cached.status_code==200 and cached.headers['content-type']=='image/jpeg'
    assert cached.content==base64.b64decode(result['preview'])
    assert social.client().get('/api/post-images/'+asset['id']).status_code==401
    metadata=client.get('/api/observations/'+identity+'/images').json()
    assert metadata['images'][0]['ocr_text'].startswith('HALLOWEEN') and 'cdninstagram.com' not in json.dumps(metadata)
    with social.factory() as db:
        assert db.get(Observation,identity).caption==caption and db.get(EventCandidate,old_id).status=='approved'
        ocr=next(c for c in db.query(EventCandidate) if c.fields.get('evidence',{}).get('method')=='local_poster_ocr_v1')
        assert ocr.status=='needs_review' and 'poster_text_review' in ocr.missing and ocr.fields['event_date']=='2030-10-31'
        assert not db.get(Publisher,p.id).enabled
        from app.models.event import Event
        assert db.query(Event).count()==0

def test_retry_and_duplicate_slide_do_not_duplicate_drafts(social,announcement):
    _,worker,_,identity,owner,asset=leased(social,announcement);message=str(uuid.uuid4());result=poster_result()
    assert deliver(worker,owner,asset,result,message).status_code==200
    assert deliver(worker,owner,asset,result,message).json()['new_candidates']==1
    with social.factory() as db:
        db.add(PostImage(observation_id=identity,source_url='https://scontent.cdninstagram.com/slide2.jpg',source_hash='a'*64,position=1));db.commit()
    second=worker.post('/media/lease',json={'owner':owner}).json()['image']
    assert deliver(worker,owner,second,result).json()['new_candidates']==0
    with social.factory() as db:assert db.query(DeliveryReceipt).count()==2

@pytest.mark.parametrize('change',[{'preview':'PHN2Zz48c2NyaXB0Pjwvc2NyaXB0Pjwvc3ZnPg=='},{'image_hash':'a'*64},{'width':4},{'ocr_text':'x'*3501}])
def test_bad_preview_rejected_atomically(social,announcement,change):
    _,worker,_,_,owner,asset=leased(social,announcement)
    assert deliver(worker,owner,asset,poster_result()|change).status_code==422
    with social.factory() as db:assert db.get(PostImage,asset['id']).preview is None and db.query(DeliveryReceipt).count()==0

def test_unreadable_ocr_keeps_preview_and_caption(social,announcement):
    client,worker,_,_,owner,asset=leased(social,announcement)
    result=prepare(image_bytes(),ocr=lambda image:('',0,'timeout'))
    assert deliver(worker,owner,asset,result).json()['new_candidates']==0
    assert client.get('/api/post-images/'+asset['id']).status_code==200

def test_capture_survives_gateway_outage_without_refetch(social,announcement,monkeypatch,tmp_path):
    client,worker,_,identity=source(social,announcement)
    monkeypatch.setenv('SOCIAL_MEDIA_ENABLED','true');monkeypatch.delenv('APIFY_API_TOKEN',raising=False)
    box=Outbox(tmp_path/'outbox.db');send=send_for(worker);calls=[];down=True
    def capture(url):calls.append(url);return poster_result()
    def flaky(path,**kw):
        if down and path=='/outbox/deliver':raise urllib.error.URLError('offline')
        return send(path,**kw)
    with pytest.raises(urllib.error.URLError):cycle(box,flaky,'test',media_capture=capture)
    assert box.status()['messages_pending']==1;box.close();box=Outbox(tmp_path/'outbox.db');down=False
    cycle(box,flaky,'test',media_capture=capture)
    assert not box.status()['work_pending'] and len(calls)==1;box.close()
    assert client.get('/api/observations/'+identity+'/images').json()['images'][0]['state']=='ready'

def test_retention_removes_image_with_post(social,announcement):
    client,worker,_,identity,owner,asset=leased(social,announcement)
    assert deliver(worker,owner,asset,poster_result()).status_code==200
    with social.factory() as db:
        db.get(Observation,identity).retention_until=time.time()-1;db.commit();prune(db)
        assert db.get(PostImage,asset['id']) is None
    assert client.get('/api/post-images/'+asset['id']).status_code==404

def test_wrong_owner_and_suspended_source_cannot_deliver(social,announcement):
    _,worker,p,_,owner,asset=leased(social,announcement)
    assert deliver(worker,'x'*43,asset,poster_result()).status_code==409
    with social.factory() as db:db.get(Publisher,p.id).approval='suspended';db.commit()
    assert deliver(worker,owner,asset,poster_result()).status_code==409

@pytest.mark.parametrize('url',['http://scontent.cdninstagram.com/a.jpg','https://127.0.0.1/a.jpg','https://x.fbcdn.net.evil.test/a.jpg','https://evil.test/a.jpg','https://scontent.cdninstagram.com@127.0.0.1/a.jpg'])
def test_image_fetch_denies_untrusted_destinations(url):
    with pytest.raises(AccessFailure):fetch(url,media=True)

def test_preview_limit_svg_rejection_and_missing_engine():
    assert len(base64.b64decode(poster_result()['preview']))<=40000
    with pytest.raises(Exception):prepare(b'<svg><script/></svg>')
    assert read_text(Image.new('RGB',(20,20)),executable='/nonexistent-tesseract')[2]=='unavailable'


@pytest.mark.skipif(not __import__('os').getenv('TEST_POSTGRES_URL'),reason='Disposable PostgreSQL not configured')
def test_real_postgres_image_receipt_privileges_and_retention(monkeypatch):
    import os,subprocess,sys
    from pathlib import Path
    from sqlalchemy import create_engine,text,event
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker
    from app.social.models import Staff
    from app.social.post_images import Lease,lease
    from app.social.delivery import Delivery,deliver as commit_delivery
    url=make_url(os.environ['TEST_POSTGRES_URL']);name='poster_'+uuid.uuid4().hex
    admin=create_engine(url,isolation_level='AUTOCOMMIT');runtime=None;maintenance=None
    with admin.connect() as db:db.execute(text('CREATE DATABASE '+name))
    target=url.set(database=name);owner=create_engine(target);factory=sessionmaker(bind=owner,expire_on_commit=False)
    api=Path(__file__).resolve().parents[2]
    try:
        env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=api,env=env,capture_output=True,text=True);assert result.returncode==0,result.stderr
        with owner.begin() as db:db.execute(text((api.parents[1]/'infrastructure/social/roles.sql').read_text()))
        monkeypatch.setenv('SOCIAL_L4_ENABLED','true');monkeypatch.setenv('SOCIAL_MEDIA_ENABLED','true')
        monkeypatch.setenv('SOCIAL_DATABASE_URL',target.render_as_string(hide_password=False));settings.cache_clear()
        with factory() as db:
            staff=Staff(email='poster@example.org',name='Poster fixture',role='OWNER');db.add(staff);db.flush()
            p=Publisher(platform='instagram',target_type='profile',external_id='fixture_venue',url='https://www.instagram.com/fixture_venue/',name='Fixture',relevance='Synthetic Bratislava venue',approval='approved',enabled=False,collection_approved=True,eligibility='available',permission_basis='Explicit fixture approval',method='apify',created_by=staff.id);db.add(p);db.flush()
            obs=Observation(publisher_id=p.id,external_id='PosterFixture',source_url='https://www.instagram.com/p/PosterFixture/',content_hash='a'*64,caption='See poster for details',published_at='2026-10-28T00:00:00+00:00',method='apify',provenance={},media=['https://scontent.cdninstagram.com/post.jpg'],retention_until=time.time()+3600);db.add(obs);db.commit();obs_id=obs.id
        runtime=create_engine(target)
        @event.listens_for(runtime,'begin')
        def gateway_role(connection):connection.exec_driver_sql('SET LOCAL ROLE bacity_l4_gateway')
        with sessionmaker(bind=runtime,expire_on_commit=False)() as db:
            asset=lease(Lease(owner='m'*43),db)['image'];assert asset
            result=commit_delivery(Delivery(id=uuid.uuid4(),action='media:complete',identity=asset['id'],owner='m'*43,payload=poster_result()),db)
            assert result['ready'] and result['new_candidates']==1
        with factory() as db:
            assert bytes(db.get(PostImage,asset['id']).preview)==base64.b64decode(poster_result()['preview'])
            # The repair query must work on PostgreSQL JSON (not DISTINCT JSON).
            from app.social.reconcile_candidates import reconcile
            old=EventCandidate(observation_id=obs_id,ordinal=99,fields={'title':'Follow our profile','evidence':{'method':'deterministic_social_caption_v1'}},missing=['event_evidence'],confidence=.1)
            db.add(old);db.commit()
            assert reconcile(db)['archived']==1;db.commit()
            assert db.get(EventCandidate,old.id).status=='rejected'
            assert db.query(EventCandidate).filter_by(status='needs_review').count()==1
        # Real observations are immutable, including their retention timestamp.
        # Advance only the cleanup clock instead of changing stored evidence.
        from types import SimpleNamespace
        import app.social.maintenance as cleanup
        future=time.time()+7200
        monkeypatch.setattr(cleanup,'time',SimpleNamespace(time=lambda:future))
        maintenance=create_engine(target)
        @event.listens_for(maintenance,'begin')
        def maintenance_role(connection):connection.exec_driver_sql('SET LOCAL ROLE bacity_l4_maintenance')
        with sessionmaker(bind=maintenance)() as db:assert prune(db)==1
        with factory() as db:assert db.get(PostImage,asset['id']) is None
    finally:
        settings.cache_clear()
        if runtime:runtime.dispose()
        if maintenance:maintenance.dispose()
        owner.dispose()
        with admin.connect() as db:db.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
        admin.dispose()
