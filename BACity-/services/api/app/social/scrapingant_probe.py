"""Explicit opt-in, isolated live validation. Never reads the production registry.

Run on a development host with a NEW disposable SQLite state file. It records
quota reservations and stages real observations, but never invokes publication.
"""
import argparse
import json
import secrets
import time
from pathlib import Path
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from .models import SocialBase,Staff,Publisher,CollectionJob,Observation,EventCandidate
from .provider_config import provider_settings
from .provider_budget import status,reserve,settle
from .acquisition.scrapingant import Client,collect,ProviderFailure
from .acquisition.urls import normalize_target
from .workflows import stage


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly authorize provider requests for the listed profiles')
    parser.add_argument('--approved-profile',action='append',default=[],help='An explicitly approved public Instagram profile URL/username; max 3')
    parser.add_argument('--permission-attestation',required=True,help='Current permission to collect these profiles; not a platform-login credential')
    parser.add_argument('--state-path',required=True,help='New disposable validation database, never production')
    args=parser.parse_args();cfg=provider_settings()
    if not args.live or not cfg.enabled or not cfg.api_key:
        raise SystemExit('Live validation requires --live, SCRAPINGANT_ENABLED=true and a backend SCRAPINGANT_API_KEY; no requests made')
    if not 1<=len(args.approved_profile)<=3 or len(args.permission_attestation)<20:
        raise SystemExit('Provide 1–3 explicitly approved profiles and a meaningful permission attestation')
    try:targets=[normalize_target(x) for x in args.approved_profile]
    except ValueError:raise SystemExit('Invalid profile; no requests made') from None
    if any(t.platform!='instagram' or t.target_type!='profile' for t in targets):
        raise SystemExit('Only explicitly selected Instagram profiles are allowed')
    path=Path(args.state_path).expanduser().resolve()
    if path.exists():raise SystemExit('Use a new disposable validation state path')
    # Exclusive mode prevents overwriting any existing state, including a race.
    path.parent.mkdir(parents=True,exist_ok=True)
    import os
    descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(descriptor)
    engine=create_engine('sqlite:///'+str(path))
    @event.listens_for(engine,'connect')
    def keys(connection,record):connection.execute('PRAGMA foreign_keys=ON')
    SocialBase.metadata.create_all(engine);factory=sessionmaker(bind=engine,expire_on_commit=False)
    results=[]
    with factory() as db:
        staff=Staff(email='validation@localhost.test',name='Isolated validation operator',role='OWNER');db.add(staff);db.flush()
        for target in targets:
            publisher=Publisher(**vars(target),name=target.external_id,relevance='Explicitly approved isolated acquisition validation',
                approval='approved',eligibility='available',permission_basis=args.permission_attestation,permission_expires=time.time()+3600,
                method='scrapingant',enabled=True,created_by=staff.id)
            db.add(publisher);db.flush()
            job=CollectionJob(publisher_id=publisher.id,dedup_key=secrets.token_hex(32),state='running');db.add(job);db.commit()
            def quota(action,payload):
                try:
                    if action=='status':return status(db)
                    if action=='reserve':return reserve(db,job,payload['request_id'],payload['kind'],payload['target'])
                    return settle(db,job,payload['request_id'],payload['cost'],payload['snapshot'],payload['error'])
                except Exception as exc:
                    db.rollback()
                    from fastapi import HTTPException
                    if isinstance(exc,HTTPException):raise ProviderFailure(exc.detail if exc.detail in ('budget_exhausted','provider_job_request_limit','usage_unverified') else 'usage_unverified') from None
                    raise ProviderFailure('usage_unverified') from None
            result=collect({'url':publisher.url},Client(cfg.api_key),quota)
            for content in result['observations']:stage(db,publisher,content,'isolated-validation',job=job)
            job.state,job.finished,job.error=result['outcome'],time.time(),result['error'];db.commit()
            results.append({'profile':target.url,'profile_accessible':result['outcome'] in ('success','empty','partial'),
                'outcome':result['outcome'],'error':result['error'],'requests':result['requests'],'bytes_received':result['bytes_received'],
                **result['provider_metrics'],'observations_staged':len(result['observations']),
                'event_candidates':db.query(EventCandidate).join(Observation,EventCandidate.observation_id==Observation.id).filter(Observation.publisher_id==publisher.id).count()})
        print(json.dumps({'kind':'explicit_live_validation','profiles':results,'budget':status(db),'canonical_writes':0,'state_path':str(path)},indent=2))
    engine.dispose()

if __name__=='__main__':main()
