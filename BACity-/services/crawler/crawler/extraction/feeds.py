"""Bounded structured feeds. Publication dates never become event starts."""
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from urllib.parse import urljoin
import pytz
from dateutil.rrule import rrulestr
from crawler.items import RawEvent
from crawler.extraction.jsonld_extractor import extract_jsonld_events

MAX_EVENTS = 100
MAX_OCCURRENCES = 32


def extract_feed(text, source_url, now=None):
    if len(text.encode('utf-8')) > 2 * 1024 * 1024:
        return []
    if text.lstrip().startswith('BEGIN:VCALENDAR'):
        return _ical(text, source_url, now or datetime.now(timezone.utc))
    if text.lstrip().startswith(('{','[')):
        try:
            json.loads(text)
        except (ValueError,RecursionError):
            return []
        return extract_jsonld_events('<script type="application/ld+json">'+text+'</script>',source_url)[:MAX_EVENTS]
    if re.search(r'<(?:html|script)\b', text, re.I):
        return extract_jsonld_events(text, source_url)[:MAX_EVENTS]
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return extract_jsonld_events(text, source_url)[:MAX_EVENTS]
    results = []
    for item in root.iter():
        if item.tag.rsplit('}', 1)[-1] not in ('item', 'entry'):
            continue
        fields = {child.tag.rsplit('}', 1)[-1].lower(): child for child in item}
        title = fields.get('title')
        link = fields.get('link')
        url = urljoin(source_url, ((link.get('href') or link.text) if link is not None else '') or source_url)
        for key in ('description', 'encoded', 'content', 'summary'):
            content = fields.get(key)
            if content is not None:
                results.extend(extract_jsonld_events(''.join(content.itertext()), url))
        start = next((fields[k].text for k in ('startdate', 'start') if k in fields), None)
        if title is not None and start:
            results.append(RawEvent(title=''.join(title.itertext()), start_raw=start,
                end_raw=fields['enddate'].text if 'enddate' in fields else None,
                venue_name=fields['location'].text if 'location' in fields else None,
                source_url=url, original_source_url=source_url, extraction_method='feed_event', extraction_confidence=.9))
        if len(results) >= MAX_EVENTS:
            break
    return results[:MAX_EVENTS]


def _ical_date(value, parameters):
    zone = pytz.timezone(parameters.get('TZID', 'Europe/Bratislava'))
    if value.endswith('Z'):
        return datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    fmt = '%Y%m%d' if parameters.get('VALUE') == 'DATE' or len(value) == 8 else '%Y%m%dT%H%M%S'
    return zone.localize(datetime.strptime(value, fmt), is_dst=None)


def _ical(text, url, now):
    # Scope: VEVENT, explicit TZID/UTC, simple RRULE. Custom VTIMEZONE and
    # occurrence overrides are rejected, not silently reinterpreted.
    if 'BEGIN:VTIMEZONE' in text or 'RECURRENCE-ID' in text:
        return []
    text = re.sub(r'\r?\n[ \t]', '', text)
    events = []
    for block in re.findall(r'BEGIN:VEVENT\s*\n(.*?)\nEND:VEVENT', text, re.S)[:MAX_EVENTS]:
        fields = {}
        for line in block.splitlines():
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            parts = key.split(';')
            params = dict(p.split('=', 1) for p in parts[1:] if '=' in p)
            fields[parts[0]] = (value.strip(), params)
        try:
            start = _ical_date(*fields['DTSTART'])
            end = _ical_date(*fields['DTEND']) if 'DTEND' in fields else None
            summary = fields['SUMMARY'][0]
            raw = RawEvent(title=summary, start_raw=start.isoformat(), end_raw=end.isoformat() if end else None,
                duration_raw=fields.get('DURATION', (None, {}))[0],
                description=fields.get('DESCRIPTION', (None, {}))[0],
                venue_name=fields.get('LOCATION', (None, {}))[0],
                source_url=urljoin(url, fields.get('URL', (url, {}))[0]), original_source_url=url,
                event_status='cancelled' if fields.get('STATUS', ('', {}))[0] == 'CANCELLED' else 'fresh',
                extraction_method='icalendar', extraction_confidence=.95)
            starts = [start]
            if 'RRULE' in fields:
                rule_text = fields['RRULE'][0]
                allowed = {'FREQ','INTERVAL','COUNT','UNTIL','BYDAY','BYMONTHDAY','BYMONTH','WKST'}
                if len(rule_text) > 512 or any(part.split('=',1)[0] not in allowed for part in rule_text.split(';')):
                    continue
                if start < now - timedelta(days=366 * 5):
                    continue  # Bound dateutil's enumeration of historical rules.
                # A secondly/minutely rule must not consume unbounded CPU.
                if not re.match(r'FREQ=(DAILY|WEEKLY|MONTHLY|YEARLY)(;|$)', rule_text):
                    continue
                if 'COUNT=' in rule_text and int(re.search(r'COUNT=(\d+)', rule_text)[1]) > 366:
                    continue
                rule = rrulestr(rule_text, dtstart=start)
                lower = max(start, now - timedelta(days=1))
                starts = []
                for occurrence in rule.xafter(lower, count=MAX_OCCURRENCES, inc=True):
                    if occurrence > now + timedelta(days=366):
                        break
                    starts.append(occurrence)
            exclusions = set()
            if 'EXDATE' in fields:
                values, params = fields['EXDATE']
                exclusions = {_ical_date(v, params) for v in values.split(',')}
            for occurrence in starts:
                if occurrence in exclusions:
                    continue
                # Recurrences retain the explicitly provided wall-clock end;
                # normalize after calendar shifts to respect DST changes.
                occurrence = start.tzinfo.localize(occurrence.replace(tzinfo=None), is_dst=None) if hasattr(start.tzinfo, 'localize') else occurrence
                shifted_end = None
                if end:
                    wall_end = end.replace(tzinfo=None) + (occurrence.replace(tzinfo=None) - start.replace(tzinfo=None))
                    shifted_end = pytz.timezone(str(end.tzinfo)).localize(wall_end, is_dst=None) if hasattr(end.tzinfo, 'localize') else wall_end.replace(tzinfo=end.tzinfo)
                events.append(replace(raw, start_raw=occurrence.isoformat(), end_raw=shifted_end.isoformat() if shifted_end else None))
                if len(events) >= MAX_EVENTS:
                    return events
        except (KeyError, ValueError, TypeError, pytz.InvalidTimeError, pytz.UnknownTimeZoneError):
            continue
    return events
