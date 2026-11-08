"""Bounded retention cleanup, run with a maintenance-specific database role."""
import time
from sqlalchemy import select, delete, cast, String
from .models import Observation, EventCandidate, CandidateReview, Challenge, StaffSession, Invitation, RateBucket, CollectionJob, ProviderRequest, ApifyRun
from .security import audit


def prune(db,limit=100):
    now=time.time()
    expired=db.execute(select(Observation.id).where(Observation.retention_until<now).limit(limit)).scalars().all()
    if expired:
        candidates=db.query(EventCandidate.id).filter(EventCandidate.observation_id.in_(expired)).subquery()
        db.query(CandidateReview).filter(CandidateReview.candidate_id.in_(select(candidates.c.id))).delete(synchronize_session=False)
        db.query(EventCandidate).filter(EventCandidate.observation_id.in_(expired)).delete(synchronize_session=False)
        db.query(Observation).filter(Observation.id.in_(expired)).delete(synchronize_session=False)
        audit(db,'social-maintenance','observations.retention_deleted',details={'observations':len(expired)})
    for model,criterion in ((Challenge,Challenge.expires<now-86400),(Invitation,Invitation.expires<now-86400),
                            (RateBucket,RateBucket.expires<now),(StaffSession,StaffSession.created<now-28800),
                            (CollectionJob,(CollectionJob.finished<now-14*86400))):
        # FK-linked observation jobs must outlive retained observations.
        query=select(list(model.__table__.primary_key.columns)[0]).where(criterion).limit(limit)
        if model is Invitation:
            query=query.where(~select(Challenge.digest).where(Challenge.invitation_digest==Invitation.digest).exists())
        if model is CollectionJob:
            query=query.where(CollectionJob.buffered.is_(False),~select(Observation.id).where(Observation.job_id==CollectionJob.id).exists(),~select(ProviderRequest.id).where(ProviderRequest.job_id==CollectionJob.id).exists(),
                ~select(ApifyRun.id).where(ApifyRun.id==CollectionJob.apify_run_id,ApifyRun.state.in_(('planned','reserved','dispatching','running','dataset'))).exists())
        ids=db.execute(query).scalars().all()
        if ids:
            pk=list(model.__table__.primary_key.columns)[0]
            db.execute(delete(model).where(pk.in_(ids)))
    # Resumable datasets contain caption copies; clear terminal payloads on the
    # same raw-evidence schedule while retaining run IDs and billing metadata.
    from .config import settings
    old_runs=db.execute(select(ApifyRun).where(ApifyRun.finished<now-settings().observation_retention_days*86400,
        ApifyRun.state.in_(('finished','failed')),cast(ApifyRun.items,String)!='{}').limit(limit)).scalars().all()
    for run in old_runs:run.items={}
    if old_runs:audit(db,'social-maintenance','apify.payloads_retention_cleared',details={'observations':len(old_runs)})
    db.commit()
    return len(expired)


def main():
    from .db import session_factory
    from .config import settings
    from .database_policy import verify_database_policy
    with session_factory()() as db:
        cfg=settings()
        verify_database_policy(db,service_role='maintenance',consumer_role=cfg.consumer_db_role)
        print('Expired observations removed:',prune(db))

if __name__=='__main__':
    main()
