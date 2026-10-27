"""Persistent fail-closed quota. Every provider request reserves before networking.

125 credits is the largest documented v2 request mode (26 Oct 2026). We use
only browser=false/datacenter (documented 1), but hold the larger amount until
Ant-credits-cost settles it. Missing/ambiguous costs keep all 125 as estimated.
Status queries are also counted and reserved; no free status-call assumption.
"""
import time
from sqlalchemy import select,func
from fastapi import HTTPException
from .models import ProviderBudget,ProviderRequest
from .security import insert_for
from .provider_config import provider_settings

REQUEST_RESERVATION=125
USAGE_TTL=86400


def locked(db):
    db.execute(insert_for(db,ProviderBudget).values(id=1).on_conflict_do_nothing(index_elements=['id']))
    state=db.execute(select(ProviderBudget).where(ProviderBudget.id==1).with_for_update()).scalar_one()
    # Crashed/ambiguous calls never get a refund. Their full reservation is spent.
    for request in db.execute(select(ProviderRequest).where(ProviderRequest.state=='reserved',ProviderRequest.created<time.time()-120).with_for_update()).scalars():
        request.state,request.finished,request.cost,request.cost_kind='settled',time.time(),request.reserved,'estimated'
        state.reserved-=request.reserved;state.charged+=request.reserved;state.since_sync+=request.reserved;state.estimated_credits+=request.reserved
    return state


def status(db):
    cfg=provider_settings();state=db.get(ProviderBudget,1);now=time.time()
    fresh=bool(state and state.synced and now-state.synced<USAGE_TTL and state.period_start<=now<state.period_end-60)
    ceiling=min(cfg.monthly_credit_limit,state.provider_total) if state and state.provider_total is not None else cfg.monthly_credit_limit
    accounted=max(state.charged,state.provider_used+state.since_sync) if state else 0
    remaining=max(0,ceiling-cfg.monthly_credit_reserve-accounted-(state.reserved if state else 0))
    reason=(state.blocked if state else None) or ('usage_unverified' if not fresh else 'budget_exhausted' if remaining<REQUEST_RESERVATION else None)
    return {'configured':cfg.configured,'enabled':cfg.enabled,'max_profiles':cfg.max_active_profiles,'interval_hours':cfg.collection_interval_hours,
        'credit_limit':cfg.monthly_credit_limit,'credit_reserve':cfg.monthly_credit_reserve,'period_start':state.period_start if state else None,
        'period_end':state.period_end if state else None,'provider_used':state.provider_used if state else None,
        'reported_credits':state.reported_credits if state else 0,'estimated_credits':state.estimated_credits if state else 0,
        'reserved_credits':state.reserved if state else 0,'accounted_credits':accounted,'remaining_budget':remaining,
        'requests':state.requests if state else 0,'usage_requests':state.usage_requests if state else 0,
        'last_usage_sync':state.synced if state else None,'needs_sync':not fresh,'suspension_reason':reason,
        'reservation_per_request':REQUEST_RESERVATION,'precision':'estimated' if state and state.estimated_credits else 'provider_reported' if fresh else 'unverified'}


def reserve(db,job,request_id,kind,target):
    state=locked(db);cfg=provider_settings();now=time.time()
    if not cfg.enabled or not cfg.configured:
        raise HTTPException(409,'provider_not_configured')
    previous=db.get(ProviderRequest,request_id)
    if previous:
        # A retry must never authorize a second network request with the same token.
        raise HTTPException(409,'provider_request_already_reserved')
    if state.reserved:
        raise HTTPException(409,'provider_request_in_flight')
    count=db.query(ProviderRequest).filter_by(job_id=job.id,kind=kind).count()
    if count >= (1 if kind=='usage' else 3):
        raise HTTPException(409,'provider_job_request_limit')
    health=status(db)
    if kind=='acquire' and health['needs_sync']:
        raise HTTPException(409,'usage_unverified')
    if state.blocked=='provider_cost_exceeded_reservation':
        raise HTTPException(409,state.blocked)
    if kind=='acquire' and state.blocked:
        raise HTTPException(409,state.blocked)
    if kind=='usage' and not health['needs_sync'] and not state.blocked:
        raise HTTPException(409,'usage_snapshot_is_current')
    # A billing-period refresh is permitted after expiry, but no page acquisition is.
    renewing=kind=='usage' and state.period_end and now>=state.period_end
    if renewing:
        probes=db.query(ProviderRequest).filter(ProviderRequest.kind=='usage',ProviderRequest.created>=state.period_end).count()
        if probes>=min(3,(cfg.monthly_credit_limit-cfg.monthly_credit_reserve)//REQUEST_RESERVATION):
            raise HTTPException(409,'usage_unverified')
    if not renewing and health['remaining_budget']<REQUEST_RESERVATION:
        raise HTTPException(409,'budget_exhausted')
    state.reserved+=REQUEST_RESERVATION
    if kind=='usage':state.usage_requests+=1
    else:state.requests+=1
    request=ProviderRequest(id=request_id,job_id=job.id,kind=kind,target=target,period_start=state.period_start,reserved=REQUEST_RESERVATION)
    db.add(request);db.flush();db.commit()
    return {'reservation':request.id,'credits_reserved':request.reserved}


def settle(db,job,request_id,cost,snapshot=None,error=None):
    state=locked(db);request=db.get(ProviderRequest,request_id)
    if not request or request.job_id!=job.id:
        raise HTTPException(404,'provider_reservation_not_found')
    if request.state=='settled':return {'ok':True,'replayed':True}
    if snapshot is not None:
        start,end,total,remaining=(snapshot[k] for k in ('start','end','total','remaining'))
        now=time.time()
        if request.kind!='usage' or not (start<=now+300<end and end-start<=370*86400 and 0<=remaining<=total):
            raise HTTPException(422,'invalid_usage_snapshot')
        new_period=state.period_start is None or (start!=state.period_start or end!=state.period_end)
        if new_period:
            if state.period_end and (now<state.period_end or start<state.period_end-1 or end<=state.period_end):
                raise HTTPException(409,'billing_period_not_verified')
            prior=db.query(ProviderRequest).filter(ProviderRequest.created>=start,ProviderRequest.state=='settled').all()
            state.charged=sum(r.cost or 0 for r in prior)
            state.reported_credits=sum(r.cost or 0 for r in prior if r.cost_kind=='reported')
            state.estimated_credits=sum(r.cost or 0 for r in prior if r.cost_kind=='estimated')
            state.provider_used=0
            state.requests=sum(r.kind=='acquire' for r in prior)
            state.usage_requests=1+sum(r.kind=='usage' for r in prior)
            state.period_start,state.period_end=start,end
        elif total-remaining<state.provider_used:
            raise HTTPException(409,'usage_counter_regressed')
        state.provider_total,state.provider_remaining,state.provider_used=total,remaining,total-remaining
        state.synced=now;state.since_sync=0;state.blocked=None
    amount=request.reserved if cost is None else cost
    request.cost,request.cost_kind,request.state,request.finished=amount,'estimated' if cost is None else 'reported','settled',time.time()
    request.period_start=state.period_start
    state.reserved-=request.reserved;state.charged+=amount;state.since_sync+=amount
    if cost is None:state.estimated_credits+=amount
    else:state.reported_credits+=amount
    if amount>request.reserved:state.blocked='provider_cost_exceeded_reservation'
    elif request.kind=='usage' and snapshot is None:state.blocked='usage_unverified'
    elif error in ('provider_auth','provider_denied','challenge','login_required','access_denied'):
        state.blocked=error
    db.commit();return {'ok':True,'cost':amount,'cost_kind':request.cost_kind}
