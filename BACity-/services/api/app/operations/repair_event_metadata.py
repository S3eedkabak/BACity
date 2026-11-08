"""Evidence-preserving, idempotent metadata repair; dry-run unless --apply."""
import argparse,json,re
from datetime import datetime
from app.database import SessionLocal
from app.models.event import Event,EventStatus,EventCategory
from app.models.event_identity import EventOccurrence
from app.core.event_taxonomy import guess_category
from app.crud.event_identity import standalone_offer,imprecise_location,implausible_listing_range,documented_exhibition_span


def repair(db,apply=False):
    changes=[]
    for event in db.query(Event).filter(Event.merged_into_id.is_(None),Event.is_manual_override.is_(False)):
        values={};reasons=[]
        guess=guess_category(event.title,event.description,None)
        if (event.category==EventCategory.sports and guess!='Sports') or (event.category==EventCategory.nightlife and guess=='Other' and (event.start_time.year in (2000,2016) or event.title.casefold().startswith('visit of '))) or (guess=='Exhibitions' and event.category in (EventCategory.other,EventCategory.culture,EventCategory.theatre,EventCategory.food_drink)):
            values['category']=guess;values['tags']=[tag for tag in (event.tags or []) if tag not in {'sports','nightlife'}];reasons.append('venue/subword category inference replaced with event evidence')
        if re.match(r'^(cancelled|canceled|zrušené|zrusene)\s*(?://|:|[-–])',event.title,re.I) and event.status!=EventStatus.cancelled:
            values['status']='cancelled';reasons.append('publisher explicitly labels cancellation')
        if standalone_offer(event) and event.identity_kind!='offer':
            values['identity_kind']='offer';reasons.append('standalone admission pass is an offer, not a dated event')
        if implausible_listing_range(event.start_time,event.end_time,event.end_date):
            values['end_time']=None;values['end_date']=None;reasons.append('publisher catalog range exceeds five years; session schedule unverified')
        span=documented_exhibition_span(event)
        if span and (event.identity_kind!='single' or event.start_time!=span[0] or event.end_date!=span[1] or event.end_time is not None):
            values.update(identity_kind='single',start_time=span[0],end_date=span[1],end_time=None)
            reasons.append('publisher-documented exhibition span replaces admission-slot summary')
        corrected_sport=any(correction.get('before',{}).get('category')=='Sports' and correction.get('after',{}).get('category')!='Sports' for ref in event.sources for correction in (ref.facts or {}).get('canonical_metadata_corrections',[]))
        if corrected_sport and 'sports' in (event.tags or []):
            values['tags']=[tag for tag in event.tags if tag not in {'sports','nightlife'}];reasons.append('remove derived tag from corrected category')
        if imprecise_location(event) and event.latitude is not None:
            values.update(latitude=None,longitude=None);reasons.append('city centroid or multiple venues is not an exact event location')
        if not values:continue
        before={key:getattr(event,key).value if hasattr(getattr(event,key),'value') else str(getattr(event,key)) if getattr(event,key) is not None else None for key in values}
        after={key:value.isoformat() if hasattr(value,'isoformat') else value for key,value in values.items()}
        record={'event_id':str(event.id),'title':event.title,'before':before,'after':after,'reasons':reasons,'at':datetime.utcnow().isoformat()+'Z'}
        changes.append(record)
        if apply:
            if not event.sources:raise RuntimeError('No evidence row to preserve correction audit')
            for ref in event.sources:
                facts=dict(ref.facts or {});facts['canonical_metadata_corrections']=[*facts.get('canonical_metadata_corrections',[]),record];ref.facts=facts
            for key,value in values.items():setattr(event,key,value)
    # A retained source occurrence can outlive a previous parent metadata repair.
    # Preserve its original schedule in the same source audit before correcting it.
    for occurrence in db.query(EventOccurrence).filter(EventOccurrence.status.in_(['fresh','stale'])):
        start,end=occurrence.start_time,occurrence.end_time
        invalid=implausible_listing_range(start,end)
        if not invalid:continue
        event=db.get(Event,occurrence.event_id)
        record={'event_id':str(event.id),'occurrence_id':str(occurrence.id),'before':{'start_time':str(start),'end_time':str(end),'status':occurrence.status},'after':{'end_time':None,'status':'expired'},'reasons':['unknown permanent-listing schedule is not an upcoming occurrence'],'at':datetime.utcnow().isoformat()+'Z'}
        changes.append(record)
        if apply:
            if not event.sources:raise RuntimeError('No evidence row to preserve occurrence correction')
            for ref in event.sources:
                facts=dict(ref.facts or {});facts['canonical_metadata_corrections']=[*facts.get('canonical_metadata_corrections',[]),record];ref.facts=facts
            occurrence.end_time=None;occurrence.status='expired'
    if apply:db.flush()
    return changes

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    with SessionLocal() as db:
        result=repair(db,args.apply)
        if args.apply:db.commit()
        else:db.rollback()
        print(json.dumps(result,ensure_ascii=False,indent=2))
