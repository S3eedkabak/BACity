import time
from app.social.models import Observation,EventCandidate,AuditEvent,AuditHead,Invitation,Challenge
from app.social.security import verify_audit,audit,digest
from app.social.maintenance import prune


def test_retention_removes_raw_evidence_but_never_canonical_event(social,announcement):
    editor,staff,_,_=social.login('SOCIAL_EDITOR');p=social.publisher(staff)
    result=editor.post('/api/publishers/'+p.id+'/evidence',json=announcement)
    with social.factory() as db:
        db.get(Observation,result.json()['id']).retention_until=time.time()-1;db.commit()
        assert prune(db)==1
        assert db.query(Observation).count()==0 and db.query(EventCandidate).count()==0
        assert any(a.record['action']=='observations.retention_deleted' for a in db.query(AuditEvent))
        from app.models.event import Event
        assert db.query(Event).count()==0


def test_tampered_audit_and_truncated_tail_detected(social):
    with social.factory() as db:
        audit(db,'fixture','first');audit(db,'fixture','second');db.commit()
        rows=db.query(AuditEvent).order_by(AuditEvent.sequence).all();head=db.get(AuditHead,1)
        assert verify_audit(rows,head)
        assert not verify_audit(rows[:-1],head)
        rows[0].record={**rows[0].record,'actor':'forged'}
        assert not verify_audit(rows,head)


def test_audit_records_never_keep_freeform_notes_or_tokens(social):
    with social.factory() as db:
        audit(db,'fixture','test',details={'note':'token secret text must not be retained','password':'bad','outcome':'success'})
        db.commit();row=db.query(AuditEvent).one()
        assert 'token secret' not in str(row.record)
        assert 'password' not in row.record['details']
        assert len(row.record['details']['note_hash'])==64


def test_full_audit_storage_rolls_back_privileged_changes(social,monkeypatch):
    client,staff,_,_=social.login()
    monkeypatch.setenv('SOCIAL_MAX_AUDIT_EVENTS','1000')
    from app.social.config import settings
    settings.cache_clear()
    with social.factory() as db:
        db.add(AuditHead(id=1,sequence=1000,digest='a'*64));db.commit()
    response=client.post('/api/publishers',json={'url':'https://www.instagram.com/test_fixture/',
        'name':'Fixture publisher','relevance':'Bounded audit capacity test only'})
    assert response.status_code==503
    from app.social.models import Publisher
    with social.factory() as db:assert db.query(Publisher).count()==0
