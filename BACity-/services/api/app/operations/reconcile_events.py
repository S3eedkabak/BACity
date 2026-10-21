"""Dry-run by default. Apply in one transaction after taking a pg_dump backup.

Retains every original event row as a resolvable alias and snapshots it before
changing metadata; never purges canonical history or source observations.
"""
import argparse
import json
from datetime import datetime
from sqlalchemy import select, inspect, MetaData, Table, update, text
from app.database import SessionLocal
from app.models.event import Event, EventStatus, EventCategory
from app.models.event_source import EventSource
from app.models.event_identity import EventOccurrence, EventOffer, EventReconciliation
from app.crud.event_identity import match, is_offer, exhibition, record_listing, refresh_identity,card_label,date_precision,documented_exhibition_span


def snapshot(event):
    def serial(value):
        if hasattr(value,'value'):return value.value
        if hasattr(value,'isoformat'):return value.isoformat()
        if isinstance(value,(str,int,float,bool,list,dict)) or value is None:return value
        return str(value)
    return {col.name:serial(getattr(event,col.name)) for col in Event.__table__.columns}


def plan(db):
    events=list(db.scalars(select(Event).where(Event.merged_into_id.is_(None)).order_by(Event.created_at,Event.id)))
    # Stable oldest non-offer identity; offers cannot become primary cards.
    events.sort(key=lambda event:is_offer(event))
    roots=[];groups={}
    for event in events:
        for root in roots:
            reason=match(root,event)
            if reason:
                groups.setdefault(root.id,[]).append((event,reason));break
        else:roots.append(event)
    return [(root,groups[root.id]) for root in roots if root.id in groups]


def _reconcile_pass(db,apply=False):
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(82619422)'))
    groups=plan(db)
    report={'mode':'apply' if apply else 'dry-run','physical_rows':db.query(Event).count(),
        'identities_before':db.query(Event).filter(Event.merged_into_id.is_(None)).count(),
        'groups':[], 'aliases':0,'ticket_variants':0,'references_moved':0}
    inspector=inspect(db.bind);metadata=MetaData()
    related=[]
    # Retarget all actual FK relationships, not a hand-maintained bookmark-only list.
    for name in inspector.get_table_names():
        if name in {'events','event_sources','event_occurrences','event_offers','event_reconciliations'}:continue
        for fk in inspector.get_foreign_keys(name):
            if fk['referred_table']=='events':
                related.append((Table(name,metadata,autoload_with=db.bind),fk['constrained_columns'][0]))
    for root,members in groups:
        report['groups'].append({'root':str(root.id),'title':root.title,'members':[{'id':str(event.id),'title':event.title,'reason':reason[0],'confidence':reason[1]} for event,reason in members]})
        report['aliases']+=len(members)
        report['ticket_variants']+=sum(is_offer(event) for event,_ in members)
        if not apply:continue
        # Snapshot the root too so all changed fields have an audit record.
        root_before=snapshot(root)
        for event in [root]+[event for event,_ in members]:record_listing(db,root,event)
        db.flush()
        for alias,reason in members:
            before=snapshot(alias)
            before['root_before']=root_before
            before['related_records']={}
            for table,column in related:
                rows=db.execute(select(table).where(table.c[column]==alias.id)).mappings().all()
                if rows:
                    before['related_records'][table.name]=[{key:str(value) if value is not None else None for key,value in row.items()} for row in rows]
                    # A uniqueness conflict aborts the full transaction, preserving all data.
                    db.execute(update(table).where(table.c[column]==alias.id).values({column:root.id}))
            report['references_moved']+=db.query(EventSource).filter_by(event_id=alias.id).update({'event_id':root.id},synchronize_session=False)
            before['occurrences']=[]
            for occurrence in db.query(EventOccurrence).filter_by(event_id=alias.id):
                before['occurrences'].append({'id':str(occurrence.id),'start_time':str(occurrence.start_time),'status':occurrence.status})
                duplicate=db.query(EventOccurrence).filter_by(event_id=root.id,start_time=occurrence.start_time).first()
                if duplicate:
                    # Retain the historic row and ID; the identity has one active session.
                    occurrence.status='superseded'
                else:occurrence.event_id=root.id
            db.query(EventOffer).filter_by(event_id=alias.id).update({'event_id':root.id},synchronize_session=False)
            db.add(EventReconciliation(root_id=root.id,alias_id=alias.id,reason=reason[0],confidence=reason[1],before=before))
            alias.merged_into_id=root.id;alias.status=EventStatus.removed
            if root.venue_id is None and alias.venue_id:root.venue_id=alias.venue_id
            if not root.address and alias.address:root.address=alias.address
            if root.latitude is None and alias.latitude is not None:root.latitude,root.longitude=alias.latitude,alias.longitude
        if any(reason[0] in ('recurring_exhibition_content_place','publisher_recurring_market_place') for _,reason in members):
            root.identity_kind='recurring'
            if exhibition(root):root.category=EventCategory.exhibitions
            root.tags=[tag for tag in root.tags if tag not in ('sports','nightlife')]
        # Improve metadata without changing the durable identity ID. The old
        # card title/URL remains in the snapshot and original source observation.
        best=max([root]+[event for event,_ in members],key=lambda event:(not is_offer(event),not card_label(event),not date_precision(event),event.extraction_confidence*event.source_reliability))
        if best is not root and not root.is_manual_override:
            for field in ('title','description','category','source_url','source_id','extraction_confidence','source_reliability','image_url','venue_id','address'):
                if getattr(best,field) is not None:setattr(root,field,getattr(best,field))
        refresh_identity(db,root)
        db.flush()
        db.expire(root,['sources'])
        span=documented_exhibition_span(root)
        if span and not root.is_manual_override:
            root.identity_kind='single';root.start_time,root.end_date=span;root.end_time=None
    report['identities_after']=report['identities_before']-report['aliases']
    if apply:db.flush()
    return report


def reconcile(db,apply=False):
    # Metadata refinement can reveal another exact publisher relationship.
    # Compute the full fixed point in one transaction; a dry run uses a rolled
    # back savepoint, exercising FK/unique constraints without persisting data.
    savepoint=db.begin_nested() if not apply else None
    result=None
    try:
        for _ in range(16):
            step=_reconcile_pass(db,True)
            if result is None:result=step
            else:
                result['groups'].extend(step['groups'])
                for key in ('aliases','ticket_variants','references_moved'):result[key]+=step[key]
                result['identities_after']=step['identities_after']
            if step['aliases']==0:break
        else:raise RuntimeError('Identity reconciliation did not converge; transaction must be rolled back')
        result['mode']='apply' if apply else 'dry-run'
        return result
    finally:
        if savepoint is not None:savepoint.rollback()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    with SessionLocal() as db:
        report=reconcile(db,args.apply)
        if args.apply:db.commit()
        else:db.rollback()
    print(json.dumps(report,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__':main()
