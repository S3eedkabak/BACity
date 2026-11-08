"""Read-only retained-record and geographic identity diagnostics (not crawl totals)."""
import json
from collections import Counter,defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlsplit
from sqlalchemy import select
from app.database import SessionLocal
from app.models.event import Event,EventStatus
from app.models.event_source import EventSource
from app.models.event_identity import EventOccurrence,EventOffer,EventReconciliation
from app.crud.districts import collection,membership
from app.crud.event_identity import normalized,same_place,discoverable


def audit(db):
    now=datetime.utcnow();events=list(db.scalars(select(Event)));roots=[event for event in events if not event.merged_into_id]
    eligible=set(db.scalars(select(Event.id).where(discoverable(now))))
    districts={feature['properties']['id']:{'name':feature['properties']['name'],'canonical_rows':0,'distinct_identities':0,'discoverable_identities':0,'upcoming_distinct_events':0,'source_listings':0,'duplicate_aliases':0,'suspect_coordinates':0} for feature in collection()['features']}
    districts[None]={'name':'Unlocated or outside official polygons',**{k:0 for k in next(iter(districts.values())) if k!='name'}}
    exact=Counter();near=[];cross_source=0
    for event in events:
        region=districts[membership(event.latitude,event.longitude)]
        region['canonical_rows']+=1
        region['duplicate_aliases']+=int(event.merged_into_id is not None)
        if not event.merged_into_id:
            region['distinct_identities']+=1
            region['source_listings']+=len(event.sources)
            region['discoverable_identities']+=int(event.id in eligible)
            region['upcoming_distinct_events']+=int(event.id in eligible and event.start_time>=now)
            hosts={(urlsplit(ref.original_source_url or ref.source_url).hostname or '').removeprefix('www.') for ref in event.sources}
            cross_source+=int(len(hosts)>1)
            exact[(normalized(event.title),str(event.start_time),event.latitude,event.longitude)]+=1
            region['suspect_coordinates']+=int((event.latitude is None)!=(event.longitude is None) or event.latitude is not None and not(48<=event.latitude<=48.35 and 16.9<=event.longitude<=17.35))
    for index,a in enumerate(roots):
        for b in roots[index+1:]:
            if same_place(a,b) and abs((a.start_time-b.start_time).total_seconds())<=86400 and SequenceMatcher(None,normalized(a.title),normalized(b.title)).ratio()>=.8:
                near.append({'a':str(a.id),'b':str(b.id),'titles':[a.title,b.title],'starts':[str(a.start_time),str(b.start_time)],'decision':'review; not automatically merged'})
    by_source=defaultdict(lambda:{'observations':0,'identities':set(),'discoverable':set(),'exclusive':set()})
    for event in roots:
        hosts={(urlsplit(ref.original_source_url or ref.source_url).hostname or '').removeprefix('www.') for ref in event.sources}
        for ref in event.sources:
            host=(urlsplit(ref.original_source_url or ref.source_url).hostname or '').removeprefix('www.')
            by_source[host]['observations']+=1
        for host in hosts:
            if event.identity_kind!='offer':by_source[host]['identities'].add(event.id)
            if event.id in eligible:by_source[host]['discoverable'].add(event.id)
            if hosts=={host} and event.id in eligible:by_source[host]['exclusive'].add(event.id)
    spots=Counter((event.latitude,event.longitude) for event in roots if event.id in eligible and event.latitude is not None)
    return {'observed_at':now.isoformat()+'Z','raw_crawled_records':'not durably retained as raw inputs; do not infer from canonical rows',
        'retained_source_listing_observations':db.query(EventSource).count(),'canonical_physical_rows':len(events),
        'canonical_identity_roots':len(roots),'distinct_event_identities':sum(event.identity_kind!='offer' for event in roots),'identity_count_caveat':'conservative resolved identities; near matches below remain unverified',
        'discoverable_distinct_events':len(eligible),'upcoming_distinct_events':sum(event.id in eligible and event.start_time>=now for event in roots),
        'geolocated_discoverable_distinct_events':sum(event.id in eligible and event.latitude is not None and event.longitude is not None for event in roots),
        'active_multi_day_identities':sum(event.id in eligible and event.identity_kind!='recurring' and event.start_time<=now and ((event.end_time and (event.end_time-event.start_time).total_seconds()>86400) or bool(event.end_date)) for event in roots),
        'source_distinct_yield':{host:{key:len(value) if isinstance(value,set) else value for key,value in metrics.items()} for host,metrics in sorted(by_source.items())},
        'duplicate_groups_resolved':db.query(EventReconciliation.root_id).distinct().count(),
        'standalone_offer_identities':sum(event.identity_kind=='offer' for event in roots),
        'upcoming_occurrences':db.query(EventOccurrence).filter(EventOccurrence.start_time>=now,EventOccurrence.status.in_(['fresh','stale'])).count(),
        'superseded_occurrences':db.query(EventOccurrence).filter(EventOccurrence.status=='superseded').count(),
        'recurring_identities':sum(event.identity_kind=='recurring' for event in roots),
        'retained_occurrences':db.query(EventOccurrence).count(),'past_occurrences':db.query(EventOccurrence).filter(EventOccurrence.start_time<now).count(),
        'ticket_offers':db.query(EventOffer).count(),'alias_rows':db.query(EventReconciliation).count(),
        'cross_source_identity_groups':cross_source,'remaining_exact_key_groups':sum(count>1 for count in exact.values()),
        'past_or_expired_identity_rows':sum(event.status==EventStatus.expired or (event.end_time or event.start_time)<now for event in roots),
        'near_duplicate_review_groups':near,'districts':list(districts.values()),
        'coordinate_hotspots':[{'latitude':point[0],'longitude':point[1],'identities':count,'needs_review':count>=20} for point,count in spots.most_common(12)]}

if __name__=='__main__':
    with SessionLocal() as db:print(json.dumps(audit(db),ensure_ascii=False,indent=2))
