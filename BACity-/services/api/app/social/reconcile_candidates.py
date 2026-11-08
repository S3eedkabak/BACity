"""Archive untouched paragraph-derived drafts; preserve raw and human evidence.

Run as the database owner after a backup. Dry-run by default; --apply commits.
No collection/provider/public event writes are performed.
"""
from .models import Observation,Publisher,EventCandidate,CandidateReview,Control
from .extraction import extract,event_key,filtered_reason
from .security import audit


def reconcile(db,*,limit=100):
    from sqlalchemy import select
    from .security import insert_for
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()
    legacy_exists=db.query(EventCandidate.id).filter(EventCandidate.observation_id==Observation.id,
        EventCandidate.status.in_(['needs_review','qualified']),
        EventCandidate.fields['evidence']['method'].as_string()=='deterministic_social_caption_v1'
    ).exists()
    rows=db.query(Observation).filter(legacy_exists).order_by(Observation.observed,Observation.id).limit(limit).all()
    result={'observations_checked':len(rows),'archived':0,'created':0,'protected':0,'public_event_writes':0}
    for obs in rows:
        old=db.query(EventCandidate).filter_by(observation_id=obs.id).all()
        if any(c.status in ('approved','publication_queued','published') or c.reviewed_by or c.reviewed_hash or c.event_id or c.publication_requested_by or
               c.fields.get('evidence',{}).get('staff_edit') or
               db.query(CandidateReview).filter_by(candidate_id=c.id).first() for c in old):
            result['protected']+=1;continue
        legacy=[c for c in old if c.status in ('needs_review','qualified') and
                c.fields.get('evidence',{}).get('method')=='deterministic_social_caption_v1']
        for c in legacy:
            c.status='rejected'
            audit(db,'candidate-reconciliation','candidate.filtered',c.id,
                  details={'outcome':filtered_reason(obs.caption) or 'paragraphs_consolidated'})
        result['archived']+=len(legacy);db.flush()
        publisher=db.get(Publisher,obs.publisher_id)
        known={event_key(c.fields) for c in db.query(EventCandidate).join(Observation,Observation.id==EventCandidate.observation_id)
            .filter(Observation.publisher_id==publisher.id,EventCandidate.status.notin_(['rejected','duplicate']))
            .order_by(EventCandidate.created.desc()).limit(1000) if event_key(c.fields)}
        ordinal=max((c.ordinal for c in old),default=-1)+1
        structured=publisher.platform=='event_url' and obs.provenance.get('content_type')=='event'
        for item in extract(obs.caption,obs.published_at,publisher,structured_event=structured):
            key=event_key(item['fields'])
            if key and key in known:continue
            item['fields']['source_url']=obs.source_url
            db.add(EventCandidate(observation_id=obs.id,ordinal=ordinal,**item))
            ordinal+=1;result['created']+=1
            if key:known.add(key)
        audit(db,'candidate-reconciliation','observation.candidates_reconciled',obs.id,
              details={'observations':1,'outcome':'archived_'+str(len(legacy))+'_created_'+str(ordinal-max((c.ordinal for c in old),default=-1)-1)})
    db.flush();return result


def main():
    import argparse,json
    from app.database import SessionLocal
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');p.add_argument('--limit',type=int,default=100)
    args=p.parse_args()
    if not 1<=args.limit<=1000:p.error('limit must be 1–1000')
    with SessionLocal() as db:
        result=reconcile(db,limit=args.limit)
        if args.apply:db.commit()
        else:db.rollback()
        print(json.dumps({'applied':args.apply,**result}))


if __name__=='__main__':main()
