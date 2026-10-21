"""Conservative identity rules shared by ingestion and offline reconciliation.

No title-only/venue-only merges. Recurring exhibitions need publisher identity
or unusually strong repeated-content evidence at the same physical venue.
Ambiguous similar listings remain separate.
"""
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlsplit
from sqlalchemy import select, func
from app.models.event import Event, EventStatus
from app.models.event_identity import EventOccurrence, EventOffer


def normalized(value):
    from app.crud.ingestion import normalize
    return normalize(value)


def implausible_listing_range(start, end_time=None, end_date=None):
    """Very long catalog ranges are not evidence of continuous event hours."""
    until=end_time.date() if end_time else end_date
    return bool(until and (until-start.date()).days > 365*5)


def standalone_offer(value):
    # An explicit product suffix is sufficient; a play merely mentioning a pass
    # in its description is not. Preserve the original title in source facts.
    title=re.split(r'\s+[-–—:]\s+',value.title)[-1]
    return bool(re.fullmatch(r'(?:(?:festivalova|festivalovy|festival|rocna|rocny)\s+)?(?:permanentka|season pass|annual pass|membership)(?:\s+\w+)?',normalized(title)))


def imprecise_location(value):
    venue=getattr(value,'venue_name',None) or (value.venue.name if getattr(value,'venue',None) else '')
    context=normalized((venue or '')+' '+(value.address or ''))
    multiple=bool(re.search(r'\b(various venues|multiple venues|rozne miesta|viacero miest)\b',context))
    center=getattr(value,'latitude',None)==48.1486 and getattr(value,'longitude',None)==17.1077
    specific=bool(re.search(r'\d',value.address or '') or (venue and normalized(venue) not in {'bratislava','bratislava various venues'}))
    return multiple or (center and not specific)


def ticket_product(value):
    match=re.search(r'\s*(?:[-–—:]\s*)?(VIP(?:\s+fast\s+track)?|FLEXI|STANDARD(?:\s+ADMISSION)?|GENERAL ADMISSION|KLASIK|CLASSIC|MEET\s*&?\s*GREET|BACKSTAGE)\s*$',value.title,re.I)
    if not match:return None
    base=value.title[:match.start()].strip(' –—-:')
    dated=re.search(r'\s+(\d{1,2}\.\d{1,2}\.\d{4}\s+\d{1,2}:\d{2})$',base)
    if dated:
        from datetime import timezone
        from zoneinfo import ZoneInfo
        try:stated=datetime.strptime(dated[1],'%d.%m.%Y %H:%M')
        except ValueError:return None
        actual=value.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava')).replace(tzinfo=None,second=0,microsecond=0)
        if stated!=actual:return None
        base=base[:dated.start()].strip()
    elif not(exhibition(value) or re.search(r'\b(ticket|admission|vstupenk)\w*',normalized(value.description))):return None
    return (base,match[1].strip()) if len(base)>=3 else None


def canonical_title(value):
    product=ticket_product(value)
    return product[0] if product else value.title


def is_offer(value):
    return ticket_product(value) is not None


def identity_title(value):
    # Cosmetic publisher qualifiers and a matching edition year are not a new
    # identity. Artist/performer/session words are otherwise retained exactly.
    words=normalized(canonical_title(value)).split()
    edition=str(value.start_time.year)
    return ' '.join(word for word in words if word not in {'international','concert','koncert',edition})


def card_label(value):
    return bool(re.match(r'^\d{1,2}\.?\s*(?:januar|februar|march|marec|april|maj|may|jun|jul|august|september|october|oktober|november|december)\w*\b',normalized(value.title)))


def exhibition(value):
    category=getattr(value.category,'value',value.category)
    return category=='Exhibitions' or bool(re.search(r'\b(?:exhibition|vystav\w*|expozici\w*)\b',normalized(value.description)))


def documented_exhibition_span(value):
    """An actual publisher date range, never a summary inferred from slots."""
    from datetime import date, timezone
    if not exhibition(value):return None
    def parse(start,end):
        if not start or not end:return None
        try:
            beginning=datetime.fromisoformat(start)
            finish=date.fromisoformat(str(end))
        except ValueError:return None
        if (finish-beginning.date()).days < 14 or implausible_listing_range(beginning,end_date=finish):return None
        return (beginning.astimezone(timezone.utc).replace(tzinfo=None) if beginning.tzinfo else beginning,finish)
    if getattr(value,'sources',None):
        spans=[]
        for source in value.sources:
            facts=source.facts or {}
            if facts.get('identity_kind')=='offer':continue
            observed=facts.get('observed_schedule') or {}
            result=parse(observed.get('start_time'),observed.get('end_date'))
            if result:spans.append(result)
        if spans:return (min(start for start,_ in spans),max(end for _,end in spans))
    if getattr(value,'temporal_evidence',None)=='date_range':
        start=getattr(value,'start_time',None)
        end=getattr(value,'end_date',None)
        return parse(start.isoformat() if start else None,end)
    return None


def same_place(a,b):
    av=getattr(a,'venue_name',None) or (a.venue.name if getattr(a,'venue',None) else None)
    bv=getattr(b,'venue_name',None) or (b.venue.name if getattr(b,'venue',None) else None)
    venue_key=lambda value:' '.join(word for word in normalized(value).split() if word not in {'klub','club','bratislava'})
    if av and bv and venue_key(av)!=venue_key(bv) and SequenceMatcher(None,normalized(av),normalized(bv)).ratio()<.8:return False
    coords=all(getattr(v,k,None) is not None for v in (a,b) for k in ('latitude','longitude'))
    near=coords and abs(a.latitude-b.latitude)<.00135 and abs(a.longitude-b.longitude)<.002
    if coords and not near:return False
    physical_address=bool(a.address and b.address and normalized(a.address)==normalized(b.address) and re.search(r'\d',a.address))
    return bool(near or physical_address or (av and bv and venue_key(av)==venue_key(bv) and (not a.address or not b.address or normalized(a.address)==normalized(b.address))))


def source_family(value):
    # Legacy cards sometimes used a Facebook/ticket link as source_url. The
    # observed publisher permalink is stronger evidence than an outbound link.
    candidates=[getattr(value,'original_source_url',None)]
    candidates.extend(ref.original_source_url for ref in getattr(value,'sources',[]))
    original=next((url for url in candidates if url and re.search(r'/program/[^/]+/\d{4}-\d{2}-\d{2}/?$',urlsplit(url).path)),None)
    url=urlsplit(original or value.source_url)
    parts=[part for part in url.path.split('/') if part]
    if parts and re.fullmatch(r'[a-z]{2}',parts[0]):parts=parts[1:]
    if parts and re.fullmatch(r'\d{4}-\d{2}-\d{2}',parts[-1]):parts=parts[:-1]
    return ((url.hostname or '').removeprefix('www.'),'/'.join(parts))


def date_precision(value):
    explicit=getattr(value,'start_precision',None)
    if explicit:return explicit=='date'
    # Legacy event cards contain a date, not an explicit midnight performance.
    from zoneinfo import ZoneInfo
    from datetime import timezone
    local=value.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava'))
    return local.hour==local.minute==0 and any(((ref.facts or {}).get('method')=='event_card' or (ref.facts or {}).get('start_precision')=='date') for ref in getattr(value,'sources',[]))


def match(a,b):
    if not same_place(a,b):return None
    title_a,title_b=normalized(canonical_title(a)),normalized(canonical_title(b))
    seconds=abs((a.start_time-b.start_time).total_seconds())
    exact_title=normalized(a.title)==normalized(b.title)
    same_family=source_family(a)==source_family(b)
    publisher=lambda value:(urlsplit(value.source_url).hostname or '').removeprefix('www.')
    if title_a==title_b and exhibition(a) and exhibition(b) and publisher(a)==publisher(b):
        from datetime import timezone
        from zoneinfo import ZoneInfo
        for span,other in ((documented_exhibition_span(a),b),(documented_exhibition_span(b),a)):
            if not span:continue
            local=other.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava')).date() if other.start_time.tzinfo is None else other.start_time.astimezone(ZoneInfo('Europe/Bratislava')).date()
            first=span[0].replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava')).date()
            if first<=local<=span[1]:return ('publisher_exhibition_range_contains_session',.98)
    if title_a==title_b and seconds==0 and (is_offer(a) or is_offer(b)) and publisher(a)==publisher(b):
        return ('publisher_ticket_tier_place_time',.99)
    from zoneinfo import ZoneInfo
    from datetime import timezone
    local_day=lambda value:value.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava')).date()
    if same_family and local_day(a)==local_day(b) and date_precision(a)!=date_precision(b) and (exact_title or '/program/' in a.source_url or '/program/' in b.source_url):
        return ('publisher_date_refined_to_clock',.99)
    category=lambda value:getattr(value.category,'value',value.category)
    if same_family and category(a)==category(b)=='Markets' and seconds<180*86400 and (identity_title(a)==identity_title(b) or card_label(a) or card_label(b)):
        return ('publisher_recurring_market_place',.99)
    if identity_title(a)==identity_title(b):
        for series,listing in ((a,b),(b,a)):
            if getattr(series,'identity_kind','single')=='recurring' and category(series)=='Markets':
                for occurrence in getattr(series,'occurrences',[]):
                    same_day=occurrence.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava')).date()==local_day(listing)
                    if occurrence.start_time==listing.start_time or (occurrence.start_precision=='date' and same_day):
                        return ('known_market_occurrence_place_title',.99)
    if identity_title(a)==identity_title(b) and seconds==0 and not(exhibition(a) and exhibition(b)) and not(is_offer(a) or is_offer(b)):
        return ('same_title_place_start',1.)
    weekly=lambda value:bool(re.search(r'(every|each)\s+(saturday|week)|kazd\w*\s+sobot',normalized(value.description)))
    if identity_title(a)==identity_title(b) and category(a)==category(b)=='Markets' and seconds<180*86400 and ((getattr(a,'identity_kind','single')=='recurring' and weekly(b)) or (getattr(b,'identity_kind','single')=='recurring' and weekly(a))):
        return ('recurring_market_schedule_place_title',.98)
    if title_a==title_b and exhibition(a) and exhibition(b) and seconds<180*86400:
        ad,bd=normalized(a.description),normalized(b.description)
        def shingles(value):
            words=value.split();return {tuple(words[i:i+5]) for i in range(max(0,len(words)-4))}
        left,right=shingles(ad),shingles(bd)
        similarity=len(left&right)/len(left|right) if left and right else 0
        # Shared long prose is substantive evidence, not a global fuzzy threshold.
        admission=bool(re.search(r'\b(?:admission|time slot|single entry|opening hours|vstup\w*|otvarac\w*)\b',ad)) and bool(re.search(r'\b(?:admission|time slot|single entry|opening hours|vstup\w*|otvarac\w*)\b',bd))
        if admission and min(len(ad),len(bd))>=200 and similarity>=.88:
            return ('same_exhibition_place_start_content',.99) if seconds==0 else ('recurring_exhibition_content_place',.97)

    return None


def record_listing(db,event,payload):
    db.flush()
    product=ticket_product(payload)
    if product or standalone_offer(payload) or getattr(payload,'identity_kind','single')=='offer':
        label=product[1] if product else payload.title
        offer=db.scalar(select(EventOffer).where(EventOffer.event_id==event.id,EventOffer.source_url==payload.source_url,EventOffer.label==label))
        if offer is None:
            offer=EventOffer(event_id=event.id,source_url=payload.source_url,label=label)
            db.add(offer)
        offer.price=payload.price;offer.currency=payload.currency
        offer.valid_from=payload.start_time;offer.valid_until=payload.end_time
        if not product:
            event.identity_kind='offer'
            return
        if exhibition(payload):return
    from zoneinfo import ZoneInfo
    from datetime import timezone
    local=payload.start_time.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava'))
    day_start=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    day_end=(local.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)).astimezone(timezone.utc).replace(tzinfo=None)
    precision='date' if date_precision(payload) else 'time'
    daily=list(db.scalars(select(EventOccurrence).where(EventOccurrence.event_id==event.id,EventOccurrence.start_time>=day_start,EventOccurrence.start_time<day_end)))
    occurrence=next((item for item in daily if item.start_time==payload.start_time),None)
    if precision=='date' and any(item.start_precision=='time' for item in daily):return
    if occurrence is None and precision=='time':occurrence=next((item for item in daily if item.start_precision=='date'),None)
    if occurrence is None:
        occurrence=EventOccurrence(event_id=event.id,source_url=payload.source_url,start_time=payload.start_time)
        db.add(occurrence)
    occurrence.event_id=event.id;occurrence.end_time=payload.end_time
    occurrence.start_time=payload.start_time;occurrence.start_precision=precision
    occurrence.status=getattr(payload.status,'value',payload.status)
    occurrence.publisher_event_id=getattr(payload,'publisher_event_id',None)
    if getattr(payload,'identity_kind','single')=='recurring' and not documented_exhibition_span(event):event.identity_kind='recurring'


def refresh_identity(db,event,now=None):
    """A card represents next availability, never an obsolete past session."""
    now=now or datetime.utcnow()
    db.flush()
    available=list(db.scalars(select(EventOccurrence).where(EventOccurrence.event_id==event.id,
        EventOccurrence.status.in_(['fresh','stale']),func.coalesce(EventOccurrence.end_time,EventOccurrence.start_time)>=now)
        .order_by(EventOccurrence.start_time,EventOccurrence.id)))
    if available:
        active=[o for o in available if o.start_time<=now and o.end_time and o.end_time>=now]
        upcoming=[o for o in available if o.start_time>=now]
        chosen=min(upcoming,key=lambda o:o.start_time) if upcoming else active[0]
        event.start_time=chosen.start_time
        # Only recurring identities summarize availability across their sessions.
        event.end_time=max((o.end_time or o.start_time for o in available)) if event.identity_kind=='recurring' else chosen.end_time
        event.status=EventStatus.fresh if any(o.status=='fresh' for o in available) else EventStatus.stale
    elif event.identity_kind=='recurring':
        event.status=EventStatus.expired
    return event


def find_identity(db,payload):
    from app.models.event_source import EventSource
    publisher_id=getattr(payload,'publisher_event_id',None)
    if publisher_id and getattr(payload,'identity_kind','single')=='recurring':
        host=(urlsplit(payload.source_url).hostname or '').removeprefix('www.')
        ids=select(EventOccurrence.event_id).where(EventOccurrence.publisher_event_id==publisher_id,
            EventOccurrence.source_url.like('%://'+host+'/%') | EventOccurrence.source_url.like('%://www.'+host+'/%'))
        for event in db.scalars(select(Event).where(Event.id.in_(ids),Event.merged_into_id.is_(None))):
            if same_place(event,payload) and identity_title(event)==identity_title(payload):return event,('publisher_series_place',1.)
    # Indexed time bound; never scan the entire database on a map request.
    window=timedelta(days=180) if exhibition(payload) or getattr(payload.category,'value',payload.category)=='Markets' else timedelta(days=1)
    for event in db.scalars(select(Event).where(Event.merged_into_id.is_(None),Event.start_time.between(payload.start_time-window,payload.start_time+window))):
        reason=match(event,payload)
        if reason:return event,reason
    return None,None


def discoverable(now=None):
    from sqlalchemy import and_, or_
    from zoneinfo import ZoneInfo
    from datetime import timezone
    now=now or datetime.utcnow()
    local_day=now.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava')).date()
    active_session=select(EventOccurrence.id).where(EventOccurrence.event_id==Event.id,
        EventOccurrence.status.in_(['fresh','stale']),
        func.coalesce(EventOccurrence.end_time,EventOccurrence.start_time)>=now).exists()
    return and_(Event.merged_into_id.is_(None),Event.identity_kind!='offer',Event.status.in_([EventStatus.fresh,EventStatus.stale]),
        or_(and_(Event.identity_kind=='recurring',active_session),
            and_(Event.identity_kind!='recurring',or_(func.coalesce(Event.end_time,Event.start_time)>=now,Event.end_date>=local_day))))


def date_window(starts_after=None,starts_before=None):
    """Filter availability, including active ranges and future recurring sessions."""
    from sqlalchemy import and_,or_,exists
    from zoneinfo import ZoneInfo
    from datetime import timezone
    conditions=[];session_conditions=[EventOccurrence.event_id==Event.id,EventOccurrence.status.in_(['fresh','stale']),
        func.coalesce(EventOccurrence.end_time,EventOccurrence.start_time)>=datetime.utcnow()]
    if starts_after:
        lower=starts_after.astimezone(timezone.utc).replace(tzinfo=None) if starts_after.tzinfo else starts_after
        day=lower.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava')).date()
        conditions.append(or_(func.coalesce(Event.end_time,Event.start_time)>=lower,Event.end_date>=day))
        session_conditions.append(func.coalesce(EventOccurrence.end_time,EventOccurrence.start_time)>=lower)
    if starts_before:
        upper=starts_before.astimezone(timezone.utc).replace(tzinfo=None) if starts_before.tzinfo else starts_before
        conditions.append(Event.start_time<=upper);session_conditions.append(EventOccurrence.start_time<=upper)
    known=exists(select(EventOccurrence.id).where(EventOccurrence.event_id==Event.id))
    return or_(and_(Event.identity_kind=='recurring',known,exists(select(EventOccurrence.id).where(*session_conditions))),
        and_(or_(Event.identity_kind!='recurring',~known),*conditions))


def annotate_availability(db,items,starts_after=None,starts_before=None):
    """Query-specific next availability; parent identity dates stay unchanged."""
    ids=[item.id for item in items if item.identity_kind=='recurring']
    if not ids:return items
    from datetime import timezone
    conditions=[EventOccurrence.event_id.in_(ids),EventOccurrence.status.in_(['fresh','stale']),func.coalesce(EventOccurrence.end_time,EventOccurrence.start_time)>=datetime.utcnow()]
    if starts_after:
        lower=starts_after.astimezone(timezone.utc).replace(tzinfo=None) if starts_after.tzinfo else starts_after
        conditions.append(func.coalesce(EventOccurrence.end_time,EventOccurrence.start_time)>=lower)
    if starts_before:
        upper=starts_before.astimezone(timezone.utc).replace(tzinfo=None) if starts_before.tzinfo else starts_before
        conditions.append(EventOccurrence.start_time<=upper)
    found=dict(db.execute(select(EventOccurrence.event_id,func.min(EventOccurrence.start_time)).where(*conditions).group_by(EventOccurrence.event_id)).all())
    for item in items:item.next_occurrence_start=found.get(item.id)
    return items
