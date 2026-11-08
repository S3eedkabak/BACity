"""Explicit opt-in live Actor validation using a NEW disposable local gateway DB."""
import argparse
import os
import json
import time
import secrets
from decimal import Decimal
from pathlib import Path
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from .models import SocialBase,Staff,Publisher,ApifyRun,Observation,EventCandidate
from .config import settings
from .apify_config import apify_settings
from .db import database
from .acquisition.urls import normalize_target
from .acquisition.apify import Client,ACTOR
from .acquisition.apify_worker import step
from .acquisition.scrapingant import ProviderFailure


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--approved-profile',action='append',default=[])
    parser.add_argument('--permission-attestation',required=True)
    parser.add_argument('--state-path',required=True)
    parser.add_argument('--max-test-budget-usd',type=Decimal,default=Decimal('0.10'))
    args=parser.parse_args();cfg=apify_settings()
    if not args.live or not cfg.enabled or not cfg.api_token:raise SystemExit('Explicit --live, APIFY_ENABLED=true and backend token required; no requests made')
    if not 1<=len(args.approved_profile)<=3 or len(args.permission_attestation)<20 or not Decimal('0')<args.max_test_budget_usd<=Decimal('0.10'):
        raise SystemExit('Use 1–3 approved profiles, verified permission and a test budget <= $0.10')
    try:targets=[normalize_target(v) for v in args.approved_profile]
    except ValueError:raise SystemExit('Invalid explicit profile selection') from None
    if any(t.platform!='instagram' or t.target_type!='profile' for t in targets):raise SystemExit('Instagram profiles only')
    path=Path(args.state_path).expanduser().resolve();path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise SystemExit('The disposable validation state path must not exist')
    descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(descriptor)
    # Only this explicit test process activates a disposable local gateway.
    key=secrets.token_urlsafe(32);owner=secrets.token_urlsafe(32)
    os.environ.update(SOCIAL_L4_ENABLED='true',SOCIAL_L4_COLLECTION_ENABLED='true',SOCIAL_L4_PUBLICATION_ENABLED='false',
        SOCIAL_ALLOW_SQLITE='true',SOCIAL_DATABASE_URL='sqlite:///'+str(path),SOCIAL_WORKER_KEY=key)
    settings.cache_clear()
    from .worker_api import app
    engine=create_engine('sqlite:///'+str(path),connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def keys(connection,record):connection.execute('PRAGMA foreign_keys=ON')
    SocialBase.metadata.create_all(engine);factory=sessionmaker(bind=engine,expire_on_commit=False)
    def dependency():
        with factory() as db:yield db
    app.dependency_overrides[database]=dependency
    with factory() as db:
        staff=Staff(email='validation@localhost.test',name='Isolated Actor validation',role='OWNER');db.add(staff);db.flush()
        for target in targets:db.add(Publisher(**vars(target),name=target.external_id,relevance='Explicit isolated validation profile',
            created_by=staff.id,approval='approved',eligibility='available',method='apify',posts_per_profile=1,enabled=True,
            permission_basis=args.permission_attestation,permission_expires=time.time()+3600))
        db.commit()
    http=TestClient(app,headers={'X-Social-Worker-Key':key,'X-Social-Lease':owner});client=Client(cfg.api_token)
    ceiling=int(args.max_test_budget_usd*1000000);deadline=time.monotonic()+600
    try:
        while time.monotonic()<deadline:
            response=http.post('/apify/lease',json={'owner':owner})
            if response.status_code!=200:raise SystemExit('Disposable gateway could not authorize validation')
            batch=response.json()['run']
            if batch is None:break
            def call(action,payload):
                result=http.post('/apify/runs/'+batch['id']+'/'+action,json=payload or {})
                if result.status_code!=200:raise ProviderFailure('billing_unverified')
                data=result.json()
                if action=='reserve' and data['reservation']>ceiling:
                    http.post('/apify/runs/'+batch['id']+'/finish',json={'error':'cancelled'})
                    raise SystemExit('Conservative reservation exceeds the strict test budget; no Actor launched')
                return data
            step(batch,client,call)
            with factory() as db:
                if not db.query(ApifyRun).filter(ApifyRun.state.in_(('planned','reserved','dispatching','running','dataset'))).count():break
            time.sleep(3)
        with factory() as db:
            runs=db.query(ApifyRun).all();profiles=[]
            for p in db.query(Publisher):
                items=[item for run in runs for member in run.members if member['publisher_id']==p.id for item in run.items.get(member['job_id'],[])]
                profiles.append({'profile':p.url,'items_returned':len(items),'posts':sum('/p/' in v['source_url'] for v in items),
                    'reels':sum('/reel/' in v['source_url'] for v in items),'captions':sum(bool(v['caption']) for v in items),
                    'timestamps':sum(bool(v['published_at']) for v in items),'media':sum(bool(v['media']) for v in items),
                    'one_item_limit_respected':len(items)<=1,'selection_rule':'newest timestamps within the returned, validated dataset',
                    'independent_instagram_newest_verification':False,
                    'full_combined_feed_reels_newest_verified':False,'last_error':p.last_error})
            print(json.dumps({'kind':'explicit_live_validation','actor':ACTOR,'profiles':profiles,'actor_runs_created':sum(bool(r.run_id) for r in runs),
                'runs':[{'id':r.run_id,'state':r.state,'reported_run_cost_micro_usd':r.cost,'reservation_micro_usd':r.reservation,'cost_kind':r.cost_kind,'error':r.error} for r in runs],
                'dataset_records_returned':sum(r.total or 0 for r in runs),'max_test_budget_micro_usd':ceiling,'api_requests':client.requests,'bytes_received':client.bytes,
                'observations_staged':db.query(Observation).count(),'event_candidates':db.query(EventCandidate).count(),'canonical_writes':0,
                'incomplete_runs_retained':any(r.state in ('running','dispatching','dataset') for r in runs),'state_path':str(path)},indent=2))
    finally:app.dependency_overrides.pop(database,None);http.close();engine.dispose()

if __name__=='__main__':main()
