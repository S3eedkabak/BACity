"""Conservative caption extraction. Missing/ambiguous fields stay private."""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Bratislava')
MONTHS = {'januar':1,'januara':1,'january':1,'leden':1,'ledna':1,
 'februar':2,'februara':2,'february':2,'unor':2,'unora':2,
 'marec':3,'marca':3,'march':3,'brezen':3,'brezna':3,
 'april':4,'aprila':4,'aprilu':4,'duben':4,'dubna':4,
 'maj':5,'maja':5,'may':5,'kveten':5,'kvetna':5,
 'jun':6,'juna':6,'june':6,'cerven':6,'cervna':6,
 'jul':7,'jula':7,'july':7,'cervenec':7,'cervence':7,
 'august':8,'augusta':8,'augusta':8,'augustu':8,'august':8,'srpen':8,'srpna':8,
 'september':9,'septembra':9,'september':9,'zari':9,
 'oktober':10,'oktobra':10,'october':10,'rijen':10,'rijna':10,
 'november':11,'novembra':11,'listopad':11,'listopadu':11,
 'december':12,'decembra':12,'december':12,'prosinec':12,'prosince':12}
NUMERIC = re.compile(r'(?<!\d)(?:(\d{4})-(\d{2})-(\d{2})|(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})?)(?!\d)')
NAMED = re.compile(r'\b(\d{1,2})\.?\s+('+ '|'.join(sorted(MONTHS, key=len, reverse=True)) + r')\s*(\d{4})?\b')
NAMED_FIRST = re.compile(r'\b('+ '|'.join(sorted(MONTHS,key=len,reverse=True))+r')\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s*(\d{4})?\b')
ISO_STAMP = re.compile(r'\d{4}-\d{2}-\d{2}[tT ]\d{2}:\d{2}(?::\d{2})?(?:[zZ]|[+-]\d{2}:\d{2})')
CLOCK = re.compile(r'(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)')


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def local_time(day, hour, minute):
    naive = datetime(day.year, day.month, day.day, hour, minute)
    valid = []
    for fold in (0, 1):
        value = naive.replace(tzinfo=TZ, fold=fold)
        if value.astimezone(timezone.utc).astimezone(TZ).replace(tzinfo=None) == naive:
            valid.append(value)
    if not valid or (len(valid) == 2 and valid[0].utcoffset() != valid[1].utcoffset()):
        return None
    return valid[0]


def extract(caption, published_at, publisher, *, now=None):
    now = now or datetime.now(timezone.utc)
    reference = None
    try:
        if published_at:
            reference = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            if reference.tzinfo is None or reference > now + timedelta(minutes=5):
                reference = None
    except (TypeError, ValueError):
        pass
    results = []
    # An explicit separate line/block is required for multiple-event extraction.
    blocks = [block.strip() for block in re.split(r'\n\s*\n', caption[:20000]) if block.strip()][:20]
    for block in blocks:
        text = normalized(block)
        dates = []
        iso_stamps=[]
        for m in ISO_STAMP.finditer(text):
            try:
                stamp=datetime.fromisoformat(m[0].upper().replace('Z','+00:00')).astimezone(TZ)
                iso_stamps.append((m.span(),stamp))
                dates.append((stamp.date(),m[0]))
            except ValueError:
                continue
        for match in NUMERIC.finditer(text):
            if any(a<=match.start()<b for (a,b),_ in iso_stamps):
                continue
            year, month, day, d, m, y = match.groups()
            explicit = year or y
            if not explicit and not reference:
                continue
            try:
                event_day = datetime(int(explicit or reference.astimezone(TZ).year), int(month or m), int(day or d)).date()
                dates.append((event_day, match.group(0)))
            except ValueError:
                continue
        for match in NAMED.finditer(text):
            d, m, y = match.groups()
            if not y and not reference:
                continue
            try:
                dates.append((datetime(int(y or reference.astimezone(TZ).year), MONTHS[m], int(d)).date(), match.group(0)))
            except ValueError:
                continue
        for match in NAMED_FIRST.finditer(text):
            m,d,y=match.groups()
            if not y and not reference:
                continue
            try:
                dates.append((datetime(int(y or reference.astimezone(TZ).year),MONTHS[m],int(d)).date(),match.group(0)))
            except ValueError:
                continue
        for word, offset in [('zajtra',1),('zitra',1),('tomorrow',1),('dnes',0),('dneska',0),('today',0),('tonight',0)]:
            if re.search(r'\b'+word+r'\b', text) and reference:
                dates.append(((reference.astimezone(TZ)+timedelta(days=offset)).date(), word))
        unique = sorted({d for d, _ in dates})
        missing = []
        if len(unique) != 1:
            missing.append('unambiguous_date')
        clocks = [m.groups() for m in CLOCK.finditer(text) if not any(a<=m.start()<b for (a,b),_ in iso_stamps)]
        if iso_stamps:
            if len(iso_stamps)!=1 or clocks:
                missing.append('unambiguous_time')
            clocks=[(str(iso_stamps[0][1].hour),str(iso_stamps[0][1].minute))]
        if len(clocks) > 2:
            missing.append('unambiguous_time')
        day = unique[0] if len(unique) == 1 else None
        start = iso_stamps[0][1] if len(iso_stamps)==1 else local_time(day, *map(int, clocks[0])) if day and clocks else None
        if day and clocks and not iso_stamps and re.search(CLOCK.pattern+r'\s*(?:utc|gmt)\b',text):
            start=datetime(day.year,day.month,day.day,*map(int,clocks[0]),tzinfo=timezone.utc).astimezone(TZ)
        if not iso_stamps and re.search(r'\b(?:cet|cest)\b',text):
            missing.append('timezone_review')
        if not clocks:
            missing.append('start_time')
        elif day and not start:
            missing.append('valid_local_time')
        end = local_time(day, *map(int, clocks[1])) if day and len(clocks) == 2 else None
        if end and start and end < start:
            missing.append('end_after_start')
        venue = publisher.venue_name
        if not venue or normalized(venue) not in text:
            missing.append('venue_evidence')
        coords = publisher.latitude, publisher.longitude
        if not all(v is not None for v in coords) or not (48 <= (coords[0] or 0) <= 48.35 and 16.9 <= (coords[1] or 0) <= 17.35):
            missing.append('verified_bratislava_location')
        if not re.search(r'\b(koncert|concert|party|vystav\w*|exhibition|festival|workshop|trh|market|prednask\w*|lecture|divadlo|theatre|premier\w*|diskusi\w*|beseda|discussion|talk|promit\w*|premiet\w*|screening|meetup|vernisaz\w*)\b', text):
            missing.append('event_evidence')
        if re.search(r'\b(zrusen\w*|zruseno|cancelled|canceled|presunut\w*|postponed|rescheduled)\b', text):
            missing.append('schedule_change_review')
        if day and day < now.astimezone(TZ).date() or start and start <= now:
            missing.append('upcoming_date')
        if reference and now-reference > timedelta(days=180):
            missing.append('old_announcement')
        title = block.splitlines()[0].strip()[:200]
        if len(title) < 3:
            missing.append('title')
        fields = {'title': title, 'description': block, 'start_time': start.astimezone(timezone.utc).isoformat() if start else None,
            'event_date': start.astimezone(TZ).date().isoformat() if start else day.isoformat() if day else None, 'start_precision': 'time' if start else 'date',
            'end_time': end.astimezone(timezone.utc).isoformat() if end and start and end >= start else None,
            'venue_name': venue, 'address': publisher.address, 'latitude': coords[0], 'longitude': coords[1],
            'source_url': publisher.url, 'timezone': 'Europe/Bratislava', 'category': 'Other',
            'evidence': {'date_fragments': [s for _,s in dates], 'time_fragments': [':'.join(c) for c in clocks],
                         'venue_in_caption': 'venue_evidence' not in missing, 'method': 'deterministic_social_caption_v1'}}
        price = re.search(r'\b(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:eur\b|€)', text)
        fields['price'] = float(price[1].replace(',', '.')) if price else 0 if re.search(r'\b(free|zdarma|volny vstup)\b', text) else None
        fields['currency'] = 'EUR' if fields['price'] is not None else None
        organizer=re.search(r'(?:organizuje|organizator|organizátor|organized by|organised by)\s*:?\s*([^\n]{3,160})',block,re.I)
        fields['organizer_name']=organizer[1].strip() if organizer else None
        ticket=re.search(r'https://[^\s<>\"\']{5,500}',block)
        fields['ticket_url']=ticket[0].rstrip('.,)') if ticket else None
        confidence = 0.9 if not missing else max(0.1, 0.8-0.1*len(missing))
        results.append({'fields': fields, 'missing': sorted(set(missing)), 'confidence': confidence,
                        'status': 'qualified' if not missing else 'needs_review'})
    return results
