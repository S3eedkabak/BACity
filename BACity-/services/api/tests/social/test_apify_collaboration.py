"""Explicit collaboration attribution and paid-dataset repair regressions."""
import pytest
from app.social.acquisition.apify import ACTOR_ID,normalize_record
from app.social.acquisition.apify_worker import step
from app.social.acquisition.scrapingant import ProviderFailure
from app.social.models import Publisher,CollectionJob,ApifyRun,ApifyBudget,Observation,EventCandidate,AuditEvent,Control
from app.social.recover_apify import recover
from .test_apify import apify,item,Provider,lease,call_for


def collaboration():
    return item()|{'ownerUsername':'fixture_promoter','coauthorProducers':[{'username':'fixture_venue','is_unpublished':False}],
        'taggedUsers':[{'username':'fixture_venue'}]}


def members():return [{'handle':'fixture_venue','job_id':'job','checkpoint_timestamp':None}]


def test_explicit_collaboration_is_attributed_to_requested_profile():
    job,content,error=normalize_record(collaboration(),members())
    assert job=='job' and error is None
    assert content['publisher_identifier']=='fixture_venue' and content['source_author']=='fixture_promoter'
    assert content['source_relationship']=='coauthor'
    assert 'taggedUsers' not in content and 'coauthorProducers' not in content


@pytest.mark.parametrize('change',[
    {'coauthorProducers':[]},{'coauthorProducers':[{'username':'somebody_else'}]},
    {'coauthorProducers':[{'username':'fixture_venue','is_unpublished':True}]},
    {'coauthorProducers':'fixture_venue'},{'coauthorProducers':[None,{'username':None}]},
    {'inputUrl':None},{'inputUrl':'https://www.instagram.com/unapproved/'},
    {'coauthorProducers':None,'mentions':['fixture_venue'],'taggedUsers':[{'username':'fixture_venue'}]},
])
def test_mentions_tags_or_unverified_source_cannot_authorize_a_collaboration(change):
    with pytest.raises(ProviderFailure,match='invalid_content'):
        normalize_record(collaboration()|change,members())


def test_collaboration_and_own_post_complete_same_batch_without_extra_launch(apify):
    social,_,_,_,_,_=apify;batch=lease(apify)
    provider=Provider([collaboration(),item(code='OwnPostTwo')],cost=0.0054)
    step(batch,provider.client(),call_for(apify,batch))
    with social.factory() as db:
        assert db.get(ApifyRun,batch['id']).state=='finished'
        observations=db.query(Observation).all();assert len(observations)==2
        collab=next(o for o in observations if o.external_id=='FixturePost')
        assert collab.provenance['publisher_identifier']=='fixture_venue'
        assert collab.provenance['source_author']=='fixture_promoter' and collab.provenance['source_relationship']=='coauthor'
    assert len(provider.launches)==1


def failed_paid_run(apify):
    social,_,p,_,_,_=apify;batch=lease(apify)
    # Simulate the old parser's rejection, then supply the complete proof.
    provider=Provider([collaboration()|{'coauthorProducers':[]},item(code='OwnPostTwo')],cost=0.0054)
    step(batch,provider.client(),call_for(apify,batch))
    evidence={'run':{'id':'ActorRun123','actId':ACTOR_ID,'status':'SUCCEEDED','defaultDatasetId':'Dataset123'},
        'metadata':{'id':'Dataset123','itemCount':2},'items':[collaboration(),item(code='OwnPostTwo')]}
    with social.factory() as db:
        run=db.get(ApifyRun,batch['id']);assert run.state=='failed' and run.error=='invalid_content'
        publisher=db.get(Publisher,p.id);publisher.enabled=False;db.commit()
        snapshot={'budget':{k:getattr(db.get(ApifyBudget,1),k) for k in ('spent','reserved','since_sync','estimated')},
            'cost':run.cost,'cost_kind':run.cost_kind,'last_attempt':publisher.last_attempt,'next_due':publisher.next_due}
    return batch,evidence,snapshot,provider


def test_owner_repairs_existing_paid_dataset_once_without_reenabling_or_rebilling(apify):
    social,_,p,_,_,_=apify;batch,evidence,before,provider=failed_paid_run(apify)
    with social.factory() as db:
        result=recover(db,batch['id'],evidence,allow_paused=True);db.commit()
        assert result=={'replayed':False,'new_observations':2,'new_candidates':1,'public_event_writes':0,'publishers_still_paused':1}
        publisher=db.get(Publisher,p.id);assert not publisher.enabled and publisher.last_error is None
        assert publisher.last_attempt==before['last_attempt'] and publisher.next_due==before['next_due']
        run=db.get(ApifyRun,batch['id']);assert run.state=='finished' and run.offset==run.total==2 and run.error is None
        assert run.cost==before['cost'] and run.cost_kind==before['cost_kind']
        assert {k:getattr(db.get(ApifyBudget,1),k) for k in before['budget']}==before['budget']
        assert db.query(CollectionJob).one().metrics['recovered_existing_dataset']
        assert db.query(Observation).count()==2 and db.query(EventCandidate).count()==1
        repeated=recover(db,batch['id'],evidence,allow_paused=True);db.commit()
        assert repeated['replayed'] and repeated['new_observations']==0
        assert db.query(Observation).count()==2
        assert db.query(AuditEvent).filter(AuditEvent.record['action'].as_string()=='apify.dataset_recovered').count()==1
        from app.models.event import Event
        assert db.query(Event).count()==0
    assert len(provider.launches)==1


@pytest.mark.parametrize('condition',['paused','suspended','edited','blocked','emergency','incomplete','wrong_dataset','wrong_run','bad_record'])
def test_repair_requires_original_evidence_and_does_not_bypass_restrictions(apify,condition):
    social,_,p,_,_,_=apify;batch,evidence,_,_=failed_paid_run(apify)
    with social.factory() as db:
        publisher=db.get(Publisher,p.id)
        if condition=='suspended':publisher.approval='suspended'
        if condition=='edited':publisher.approval='pending';publisher.collection_approved=False
        if condition=='blocked':publisher.eligibility='blocked'
        if condition=='emergency':db.get(Control,1).emergency_stop=True
        db.commit()
        if condition=='incomplete':evidence['items']=evidence['items'][:1]
        if condition=='wrong_dataset':evidence['metadata']['id']='OtherDataset'
        if condition=='wrong_run':evidence['run']['id']='OtherRun'
        if condition=='bad_record':evidence['items'][1]['ownerUsername']='unapproved'
        with pytest.raises((ValueError,ProviderFailure)):
            recover(db,batch['id'],evidence,allow_paused=condition!='paused')
        db.rollback()
        assert db.query(Observation).count()==0 and db.get(ApifyRun,batch['id']).state=='failed'
