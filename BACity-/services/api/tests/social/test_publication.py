import time
from unittest.mock import Mock
from sqlalchemy import select, delete
from app.models.event import Event
from app.models.event_source import EventSource
from app.social.config import settings
from app.social.models import EventCandidate,Observation,Publisher
from app.social.publication import deliver_one


def test_true_canonical_integration_duplicate_identity_and_shadow_no_mutations(social,announcement,monkeypatch):
    editor,staff,_,_=social.login('SOCIAL_EDITOR');publisher=social.publisher(staff)
    editor.post('/api/publishers/'+publisher.id+'/evidence',json=announcement)
    c=editor.get('/api/candidates').json()['items'][0]
    reviewer,_,_,_=social.login('SOCIAL_REVIEWER')
    approver,_,_,_=social.login('SOCIAL_ADMIN')
    assert reviewer.post('/api/candidates/'+c['id']+'/review',json={'decision':'approved','note':'Explicit evidence and date verified independently'}).status_code==200
    with social.factory() as db:
        assert deliver_one(db) is None
        assert db.query(Event).count()==0
    monkeypatch.setenv('SOCIAL_L4_PUBLICATION_ENABLED','true');settings.cache_clear()
    assert reviewer.post('/api/candidates/'+c['id']+'/publish').status_code==403
    assert approver.post('/api/candidates/'+c['id']+'/publish').status_code==200
    with social.factory() as db:
        event_id=deliver_one(db)
        assert event_id
        assert db.query(Event).count()==1
        assert db.get(EventCandidate,c['id']).status=='published'
        assert deliver_one(db) is None
        event=db.query(Event).one()
        baseline=event.identity_kind
    # Real pure comparator; a mutating ingestion helper must never be called here.
    monkeypatch.setattr('app.crud.ingestion.find_canonical_event',Mock(side_effect=AssertionError('No identity mutations')))
    response=editor.get('/api/candidates/'+c['id']+'/matches')
    assert response.status_code==200,response.text
    assert response.json()['classification']=='already_present'
    assert len(response.json()['matches'])==1
    with social.factory() as db:
        assert db.query(Event).one().identity_kind==baseline
        assert db.query(EventSource).count()==1
        # The additive staging FK must preserve the canonical deletion lifecycle.
        from app.models.event_identity import EventOccurrence, EventOffer
        db.query(EventOffer).delete();db.query(EventOccurrence).delete()
        db.query(EventSource).delete()
        db.execute(delete(Event));db.commit();db.expire_all()
        assert db.get(EventCandidate,c['id']).event_id is None


def test_publication_rechecks_offboarding_approval_evidence_and_retention(social,announcement,monkeypatch):
    editor,staff,_,_=social.login('SOCIAL_EDITOR');publisher=social.publisher(staff)
    editor.post('/api/publishers/'+publisher.id+'/evidence',json=announcement)
    c=editor.get('/api/candidates').json()['items'][0]
    admin,_,_,_=social.login('SOCIAL_ADMIN')
    assert admin.post('/api/candidates/'+c['id']+'/review',json={'decision':'approved','note':'Verified the original fixture evidence'}).status_code==200
    monkeypatch.setenv('SOCIAL_L4_PUBLICATION_ENABLED','true');settings.cache_clear()
    # Two distinct people, not two sessions for the same account.
    assert admin.post('/api/candidates/'+c['id']+'/publish').status_code==409
    owner,_,_,_=social.login()
    assert owner.post('/api/candidates/'+c['id']+'/publish').status_code==200
    with social.factory() as db:
        db.get(Publisher,publisher.id).approval='suspended';db.commit()
        assert deliver_one(db) is None
        assert db.query(Event).count()==0
        assert db.get(EventCandidate,c['id']).status=='needs_review'


def test_same_announcement_from_two_publishers_uses_existing_canonical_identity(social,announcement,monkeypatch):
    editor,staff,_,_=social.login('SOCIAL_EDITOR')
    first=social.publisher(staff)
    second=social.publisher(staff,url='https://www.instagram.com/other_fixture/',external_id='other_fixture',name='Second fixture publisher')
    reviewer,_,_,_=social.login('SOCIAL_REVIEWER');approver,_,_,_=social.login('SOCIAL_ADMIN')
    monkeypatch.setenv('SOCIAL_L4_PUBLICATION_ENABLED','true');settings.cache_clear()
    for publisher,evidence in [(first,announcement),(second,announcement|{'source_url':'https://www.instagram.com/p/SecondPost123/','external_id':'SecondPost123'})]:
        created=editor.post('/api/publishers/'+publisher.id+'/evidence',json=evidence)
        assert created.status_code==201
        items=editor.get('/api/candidates').json()['items']
        c=next(x for x in items if x['observation_id']==created.json()['id'])
        assert reviewer.post('/api/candidates/'+c['id']+'/review',json={'decision':'approved','note':'Independently verified original evidence'}).status_code==200
        assert approver.post('/api/candidates/'+c['id']+'/publish').status_code==200
        with social.factory() as db:assert deliver_one(db)
    with social.factory() as db:
        assert db.query(Event).count()==1
        assert db.query(EventSource).count()==2
        assert db.query(Publisher).count()==2
        assert len({str(c.event_id) for c in db.query(EventCandidate)})==1
