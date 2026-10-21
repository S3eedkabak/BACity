"""Publisher-declared organizer/venue URLs from explicit Bratislava Event nodes."""
import json
from crawler.extraction.jsonld_extractor import _flatten_jsonld, MAX_JSON_BYTES


def structured_source_links(response):
    size=0;result=[]
    for raw in response.css('script[type="application/ld+json"]::text').getall()[:32]:
        size+=len(raw.encode('utf-8'))
        if size>MAX_JSON_BYTES:break
        try:data=json.loads(raw)
        except (ValueError,TypeError,RecursionError):continue
        for event in _flatten_jsonld(data):
            if not event.get('name') or not event.get('startDate'):continue
            location=event.get('location') or {}
            if isinstance(location,list):location=location[0] if location else {}
            if not isinstance(location,dict):continue
            geo=location.get('geo') or {}
            try:local=48<=float(geo['latitude'])<=48.35 and 16.9<=float(geo['longitude'])<=17.35
            except (KeyError,TypeError,ValueError):local='bratislava' in json.dumps(location,ensure_ascii=False).lower()
            if not local:continue
            for key,label in (('organizer','Organizer website'),('location','Venue calendar')):
                entities=event.get(key) or []
                if not isinstance(entities,list):entities=[entities]
                for entity in entities[:8]:
                    if not isinstance(entity,dict):continue
                    url=entity.get('url')
                    if isinstance(url,str):result.append((url,label))
                    if len(result)>=20:return result
    return result
