"""Conservative adapters for observed public event markup, never news dates."""
import re
from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup
from crawler.items import RawEvent


def _metadata(soup):
    def value(prop):
        tag=soup.select_one(f'meta[property="{prop}"]')
        return tag.get('content') if tag else None
    return {'description':value('og:description'), 'image_url':value('og:image')}


def extract_source_html(html, url):
    host = (urlsplit(url).hostname or '').removeprefix('www.')
    path = urlsplit(url).path
    if host not in {'a4.sk', 'bkis.sk', 'sng.sk', 'bratislava.sk','staratrznica.sk'}:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('h1')
    if host == 'staratrznica.sk':
        events=[]
        cards=[(a,a.get('href')) for a in soup.select('a.event.event-link[href]')]
        detail=soup.select_one('aside .event')
        if title and detail and re.fullmatch(r'/sk/program/[^/]+/\d{4}-\d{2}-\d{2}/?',path):
            cards=[(detail,url)]
        for card,href in cards:
            target=urljoin(url,href)
            day=re.search(r'/(\d{4}-\d{2}-\d{2})/?$',urlsplit(target).path)
            paragraphs=card.select('p')
            name=paragraphs[1].select_one('strong') if len(paragraphs)>1 else None
            name=name or (title if card is detail else None)
            clock=re.search(r'\d{1,2}:\d{2}(?:\s*[-–]\s*\d{1,2}:\d{2})?',paragraphs[1].get_text(' ',strip=True)) if len(paragraphs)>1 else None
            if not day or not name:
                continue
            events.append(RawEvent(title=name.get_text(' ',strip=True),start_raw=day[1]+(' '+clock[0] if clock else ''),
                venue_name='Stará tržnica',source_url=target,original_source_url=url,
                extraction_method='stara_event_html',extraction_confidence=.9))
        return events[:100]
    if host == 'a4.sk':
        day = re.fullmatch(r'/events/(\d{4})/(\d{2})/(\d{2})/[^/]+/?', path)
        # The date comes from the publisher's event permalink; the clock must
        # occur in the title's own header, never in related events or footers.
        header = title.parent if title else None
        clock = re.search(r'\bo\s+(\d{1,2}:\d{2})\b', header.get_text(' ', strip=True)) if header else None
        address = next((p.parent.get_text(' ',strip=True) for p in soup.select('p')
                        if 'Karpatská 2' in p.get_text() and 'Bratislava' in p.parent.get_text()), None)
        if not day or not clock or not address:
            return []
        return [RawEvent(title=title.get_text(' ',strip=True),
            start_raw='-'.join(day.groups())+'T'+clock[1], venue_name='A4 – priestor súčasnej kultúry',
            address=address, source_url=url, **_metadata(soup),
            category_hint=' '.join(a.get_text(' ',strip=True) for a in header.select('a')), extraction_method='a4_event_html', extraction_confidence=.9)]
    if host == 'bkis.sk' and path.startswith('/udalost/') and title:
        fields = {}
        for label in soup.select('p strong'):
            key = label.get_text(' ',strip=True).rstrip(':')
            if key in {'Začiatok', 'Koniec', 'Miesto', 'Adresa', 'Organizátor'}:
                text = label.find_parent('p').get_text(' ',strip=True)
                fields[key] = text.split(':',1)[-1].strip().replace('|',' ').removesuffix('hod').strip()
        if not fields.get('Začiatok') or not fields.get('Adresa'):
            return []
        return [RawEvent(title=title.get_text(' ',strip=True), start_raw=fields['Začiatok'],
            end_raw=fields.get('Koniec'), venue_name=fields.get('Miesto'), address=fields['Adresa'],
            organizer_name=fields.get('Organizátor'), source_url=url, **_metadata(soup),
            extraction_method='bkis_event_html', extraction_confidence=.9)]
    if host == 'sng.sk' and path.startswith('/en/slovak-national-gallery/events/') and title:
        # Only explicit exhibition range; biographies elsewhere contain many dates.
        date = soup.find('div', class_=lambda c: c and 'whitespace-nowrap' in c,
                         string=re.compile(r'\(\d{1,2}/\d{1,2}/\d{4}\s*-'))
        match = re.search(r'\((\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})\)',date.get_text()) if date else None
        if not match:
            return []
        def iso(value):
            d,m,y=value.split('/')
            return f'{y}-{int(m):02d}-{int(d):02d}'
        # Date-only end is retained as a date boundary, with no invented closing hour.
        return [RawEvent(title=title.get_text(' ',strip=True),start_raw=iso(match[1]),end_raw=iso(match[2]),
            venue_name='Slovak National Gallery', address='Rázusovo nábrežie 1, Bratislava',
            category_hint='exhibition',source_url=url,**_metadata(soup),extraction_method='sng_exhibition_html',extraction_confidence=.9)]
    if host == 'bratislava.sk' and path == '/kultura-a-komunity/podujatia':
        events=[]
        for heading in soup.select('h3'):
            anchor=heading.select_one('a[href]')
            content=heading.parent
            paragraphs=content.select('p')
            if not anchor or len(paragraphs)!=2:
                continue
            date=paragraphs[0].get_text(' ',strip=True)
            venue=paragraphs[1].get_text(' ',strip=True)
            if not re.match(r'\d{1,2}\.\s*\d{1,2}\.\s*\d{4}\s*,\s*\d{1,2}:\d{2}',date) or not venue:
                continue
            events.append(RawEvent(title=anchor.get_text(' ',strip=True),start_raw=date,
                venue_name=venue, source_url=urljoin(url,anchor['href']), original_source_url=url,
                extraction_method='city_event_card', extraction_confidence=.85))
        return events[:100]
    return []
