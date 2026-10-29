from datetime import datetime,timezone
import pytest
from app.social.extraction import extract,filtered_reason,event_key
from app.social.models import Observation,EventCandidate,CandidateReview,AuditEvent
from app.social.reconcile_candidates import reconcile

GIVEAWAY='''🎃 HALLOWEEN WEEK V TRAFE! SÚŤAŽ O 2× VSTUP + BOTTLE SERVICE! 👻🔥

Najstrašidelnejší týždeň v roku je tu a my máme pre teba súťaž, ktorá ťa dostane priamo do centra halloweenskej párty!

Vyhraj 2× vstup (deň si vyberieš ty) + BOTTLE SERVICE a uži si nezabudnuteľnú noc v Trafe!

🩸 AKO SA ZAPOJIŤ?

🎃 Sleduj náš profil @trafomusicbar

👻 V komentári označ osobu, s ktorou by si prišiel/prišla na párty.

🕷️ Napíš nám, akú halloweensku masku by si si vybral/a!

🍀 Držíme palce a vidíme sa na parkete! 🔥 Žrebujeme 29.10. o 19tej.

#trafomusicbar #halloweenweek #halloweenparty #sutaz'''


def parse(social,text):
    from types import SimpleNamespace
    p=SimpleNamespace(venue_name='Fixture Hall',address='Fixture Street, Bratislava',latitude=48.15,longitude=17.12,url='https://www.instagram.com/fixture_venue/')
    return extract(text,'2026-10-25T12:00:00+00:00',p,now=datetime(2026,10,28,tzinfo=timezone.utc))


def test_actual_giveaway_does_not_create_fifteen_events_or_use_draw_as_party_date(social):
    assert filtered_reason(GIVEAWAY)=='giveaway'
    assert parse(social,GIVEAWAY)==[]
    assert parse(social,'Príď na party!\n\nVyhraj vstup 31.10.2026 o 19tej!')==[]
    assert parse(social,'Follow us!\n\n#party #concert')==[]


def test_caption_paragraphs_share_title_date_venue_and_do_not_spawn_instruction_cards(social):
    result=parse(social,'Koncert Jazz Night\n\nPríďte na koncert!\n\n31.10.2026 o 19tej\n\nFixture Hall, Bratislava\n\nSleduj náš profil @fixture')
    assert len(result)==1
    assert result[0]['fields']['title']=='Koncert Jazz Night'
    assert result[0]['fields']['event_date']=='2026-10-31'
    assert result[0]['fields']['start_time']=='2026-10-31T18:00:00+00:00'
    assert 'venue_evidence' not in result[0]['missing']


@pytest.mark.parametrize('draw',['Žrebujeme 29.10. o 19tej.','Giveaway ends 29.10.2026 19:00.','Winners announced 29.10.2026 at 19h.'])
def test_real_dated_event_survives_giveaway_and_draw_deadline_is_excluded(social,draw):
    result=parse(social,'HALLOWEEN PARTY\n31.10.2026 22:00\nFixture Hall\n\nSúťaž o 2 vstupy!\n'+draw)
    assert len(result)==1
    assert result[0]['fields']['event_date']=='2026-10-31'
    assert result[0]['fields']['start_time']=='2026-10-31T21:00:00+00:00'
    assert 'unambiguous_date' not in result[0]['missing']
    assert not any('29.10' in x for x in result[0]['fields']['evidence']['date_fragments'])


def test_repeated_blocks_merge_but_different_scheduled_events_remain(social):
    one='Koncert Jazz\n2030-11-10 20:00\nFixture Hall'
    assert len(parse(social,one+'\n\n'+one))==1
    assert len(parse(social,one+'\n\n'+one.replace('11-10','11-11')))==2
    assert event_key({'title':'Jazz','event_date':'2030-11-10','venue_name':None}) is None
    from app.social.post_images import candidate_key
    assert candidate_key({'title':'Jazz','event_date':'2030-11-10'})!=candidate_key({'title':'Jazz','event_date':'2030-11-11'})


def test_reposts_keep_evidence_without_multiplying_queue_and_changed_schedule_survives(social,announcement):
    client,staff,_,_=social.login();p=social.publisher(staff)
    for i,caption in enumerate([announcement['caption'],announcement['caption']+'\n\nTickets available!',announcement['caption'].replace('20:00','21:00')]):
        body=announcement|{'caption':caption,'source_url':f'https://www.instagram.com/p/RepostTest{i}/','external_id':f'RepostTest{i}'}
        assert client.post('/api/publishers/'+p.id+'/evidence',json=body).status_code==201
    with social.factory() as db:
        assert db.query(Observation).count()==3 and db.query(EventCandidate).count()==2
        assert any(a.record['action']=='candidate.duplicate_skipped' for a in db.query(AuditEvent))


def legacy(social,announcement,caption):
    client,staff,_,_=social.login();p=social.publisher(staff)
    result=client.post('/api/publishers/'+p.id+'/evidence',json=announcement|{'caption':caption})
    identity=result.json()['id']
    with social.factory() as db:
        # Reproduce the old paragraph splitting, retaining every source unchanged.
        db.query(EventCandidate).delete()
        for ordinal,line in enumerate(caption.split('\n\n')):
            db.add(EventCandidate(observation_id=identity,ordinal=ordinal,fields={'title':line,'description':line,'evidence':{'method':'deterministic_social_caption_v1'}},missing=['event_evidence'],confidence=.1))
        db.commit()
    return client,staff,identity


def test_legacy_cleanup_archives_noise_and_keeps_original_images_posts_history(social,announcement):
    client,_,identity=legacy(social,announcement,GIVEAWAY)
    with social.factory() as db:
        before=db.query(EventCandidate).count();result=reconcile(db);db.commit()
        assert result['archived']==before and result['created']==0
        assert db.get(Observation,identity).caption==GIVEAWAY
        assert all(c.status=='rejected' for c in db.query(EventCandidate))
        assert reconcile(db)['archived']==0
    assert client.get('/api/candidates?view=active').json()['total']==0
    assert client.get('/api/candidates?view=all').json()['total']==before
    assert client.get('/api/dashboard').json()['awaiting_review']==0
    assert client.get('/api/instagram-collection').json()['event_candidates']==0


@pytest.mark.parametrize('protected',['review','staff_edit','published'])
def test_cleanup_preserves_human_work(social,announcement,protected):
    _,staff,_=legacy(social,announcement,announcement['caption'])
    with social.factory() as db:
        c=db.query(EventCandidate).one()
        if protected=='review':
            c.reviewed_by=staff.id;c.reviewed_hash='a'*64
            db.add(CandidateReview(candidate_id=c.id,actor=staff.id,decision='approved',evidence_hash='a'*64,note='Human review'))
        elif protected=='staff_edit':c.fields={**c.fields,'evidence':{**c.fields['evidence'],'staff_edit':True}}
        else:
            c.status='published'
            db.add(EventCandidate(observation_id=c.observation_id,ordinal=1,fields={'title':'Untouched old draft','evidence':{'method':'deterministic_social_caption_v1'}},missing=[],confidence=.1))
        db.commit();before=c.fields.copy();status=c.status
        result=reconcile(db);db.commit()
        assert result['archived']==0 and c.fields==before and c.status==status


def test_legacy_genuine_announcement_is_consolidated_with_complete_context(social,announcement):
    text=announcement['caption'].replace('\n','\n\n');_,_,identity=legacy(social,announcement,text)
    with social.factory() as db:
        result=reconcile(db);db.commit()
        assert result['created']==1
        active=db.query(EventCandidate).filter(EventCandidate.status!='rejected').one()
        assert active.fields['description']==text and active.fields['start_time']
        assert db.get(Observation,identity).caption==text
