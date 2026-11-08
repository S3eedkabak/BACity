"""Host-owner repair of an already paid, completed dataset. No provider calls.

Not exposed through HTTP or the collector gateway. Invoke with the migration-owner
connection in a one-off process; ordinary staff/gateway roles cannot rewrite runs.
"""
import argparse
import json
import sys
import time
from sqlalchemy import select
from .models import Publisher, CollectionJob, ApifyRun, Observation, EventCandidate, Control
from .security import audit, insert_for
from .workflows import stage
from .apify_jobs import DatasetContent
from .acquisition.apify import ACTOR_ID, normalize_record
from .acquisition.policy import MAX_POSTS


def recover(db, identity, evidence, *, allow_paused=False):
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    control=db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()
    if control.emergency_stop:
        raise ValueError('Emergency stop is active; no dataset was changed')
    run=db.execute(select(ApifyRun).where(ApifyRun.id==identity).with_for_update()).scalar_one_or_none()
    if not run:
        raise ValueError('Collection run not found')
    remote=evidence.get('run',{});metadata=evidence.get('metadata',{});records=evidence.get('items')
    if (remote.get('id')!=run.run_id or remote.get('actId')!=ACTOR_ID or remote.get('status')!='SUCCEEDED'
            or remote.get('defaultDatasetId')!=run.dataset_id or metadata.get('id')!=run.dataset_id):
        raise ValueError('Evidence must match the original successful Actor run and dataset')
    if (not isinstance(records,list) or type(metadata.get('itemCount')) is not int
            or len(records)!=metadata['itemCount'] or len(records)!=run.total or not 0<len(records)<=80):
        raise ValueError('The complete original dataset is required')
    if run.state=='finished' and run.error is None:
        jobs=[db.get(CollectionJob,m['job_id']) for m in run.members]
        if jobs and all(j and j.metrics.get('recovered_existing_dataset') for j in jobs):
            return {'replayed':True,'new_observations':0,'new_candidates':0,'public_event_writes':0}
    if (run.state!='failed' or run.error!='invalid_content' or run.provider_status!='SUCCEEDED'
            or not run.cost_kind or not run.members):
        raise ValueError('Only settled, successful Actor runs rejected as invalid content can be repaired')
    # Normalize and validate everything before staging any record. An unrelated
    # or restricted record still rejects the whole repair transaction.
    values={m['job_id']:{} for m in run.members}
    for raw in records:
        job_id,content,error=normalize_record(raw,run.members)
        if error:
            if error not in ('older_item_skipped','pinned_item_skipped'):
                raise ValueError('The original dataset contains restricted or unavailable content')
            continue
        value=DatasetContent.model_validate(content).model_dump()
        values[job_id][value['external_id']]=value
    now=time.time();members=[]
    for member in run.members:
        job=db.execute(select(CollectionJob).where(CollectionJob.id==member['job_id']).with_for_update()).scalar_one()
        p=db.execute(select(Publisher).where(Publisher.id==member['publisher_id']).with_for_update()).scalar_one()
        if (job.apify_run_id!=run.id or job.publisher_id!=p.id or job.state!='failed' or job.error!='invalid_content'
                or p.method!='apify' or p.external_id!=member['handle'] or p.approval!='approved'
                or p.eligibility!='available' or not p.permission_basis
                or not (p.collection_approved or (p.permission_expires and p.permission_expires>now))):
            raise ValueError('Publisher approval, access or original job is no longer eligible for repair')
        if not p.enabled and not allow_paused:
            raise ValueError('Publisher is paused; explicit host-owner recovery of captured results is required')
        if db.query(CollectionJob).filter(CollectionJob.publisher_id==p.id,CollectionJob.created>job.created).first():
            raise ValueError('A newer collection exists; inspect it before repairing this run')
        selected=sorted(values[job.id].values(),key=lambda v:(v['published_at'],v['external_id']),reverse=True)[:min(MAX_POSTS,member['limit'])]
        members.append((job,p,selected))
    added=0;candidate_count=0;stored={}
    for job,p,selected in members:
        new=0;new_posts=0;new_reels=0
        previous_candidates=db.query(EventCandidate).join(Observation,Observation.id==EventCandidate.observation_id).filter(Observation.job_id==job.id).count()
        for value in selected:
            if len(value['caption'])<5:
                continue
            _,created=stage(db,p,value,'local-operator',job=job)
            new+=int(created);new_posts+=int(created and '/p/' in value['source_url']);new_reels+=int(created and '/reel/' in value['source_url'])
            from datetime import datetime
            stamp=datetime.fromisoformat(value['published_at']).timestamp()
            if p.instagram_timestamp is None or stamp>p.instagram_timestamp:
                p.instagram_timestamp=stamp;p.checkpoint=value['external_id']
        total_candidates=db.query(EventCandidate).join(Observation,Observation.id==EventCandidate.observation_id).filter(Observation.job_id==job.id).count()
        usable=any(len(v['caption'])>=5 for v in selected)
        job.state='success' if usable else 'empty';job.error=None if usable else 'no_items_unverified';job.finished=now
        job.metrics={**job.metrics,'posts_discovered':len(selected),'reels_discovered':sum('/reel/' in v['source_url'] for v in selected),
            'new_observations':new,'new_posts':new_posts,'new_reels':new_reels,'new_candidates':total_candidates,
            'recovered_existing_dataset':True,'original_error':'invalid_content'}
        if usable:
            p.last_success=now;p.last_error=None;p.failures=0
        # Keep enabled, next_due and last_attempt unchanged: no extra allowance,
        # no new source request, and a paused publisher stays paused.
        stored[job.id]=selected;added+=new;candidate_count+=total_candidates-previous_candidates
    run.items=stored;run.errors={};run.offset=run.total;run.dataset_done=True
    run.state='finished';run.error=None;run.finished=now
    # The settled cost, reservation, provider run ID and all budget rows stay intact.
    audit(db,'local-operator','apify.dataset_recovered',run.id,details={
        'observations':added,'outcome':'finished','note':'Reprocessed existing paid dataset after parser correction; original failure invalid_content'})
    db.flush()
    return {'replayed':False,'new_observations':added,'new_candidates':candidate_count,'public_event_writes':0,
            'publishers_still_paused':sum(not p.enabled for _,p,_ in members)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--allow-paused',action='store_true',help='Recover captured results while leaving paused publishers paused')
    args=parser.parse_args()
    raw=sys.stdin.buffer.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:
        raise SystemExit('Recovery evidence exceeds the bounded input size')
    evidence=json.loads(raw)
    from app.database import SessionLocal
    with SessionLocal() as db,db.begin():
        result=recover(db,args.run_id,evidence,allow_paused=args.allow_paused)
    print(json.dumps(result))

if __name__=='__main__':
    main()
