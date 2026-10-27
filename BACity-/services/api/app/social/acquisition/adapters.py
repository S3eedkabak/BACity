"""Public document adapters. Fixture parsing is not evidence of live access."""
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from .urls import normalize_target
from .network import AccessFailure,fetch,fetch_document,robots_allowed

class Document(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta={}; self.scripts=[]; self.buffer=None; self.kind=None
        self.main_depth=0; self.skip_depth=0; self.visible=[]; self.visible_size=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('main','article'):
            self.main_depth+=1
        if tag in ('script','style','noscript','head'):
            self.skip_depth+=1
        if tag=='meta':
            key=attrs.get('property') or attrs.get('name')
            if key and len(self.meta)<200:
                self.meta[key]=attrs.get('content','')[:30000]
        if tag=='script' and (attrs.get('type')=='application/ld+json' or attrs.get('id')=='__UNIVERSAL_DATA_FOR_REHYDRATION__'):
            self.buffer=[]; self.kind=attrs.get('type') or attrs.get('id')
    def handle_data(self,data):
        if self.buffer is not None:
            self.buffer.append(data)
        if self.main_depth and not self.skip_depth and self.visible_size<30000:
            value=data.strip()
            if value:
                self.visible.append(value[:30000-self.visible_size]);self.visible_size+=len(value)
    def handle_endtag(self,tag):
        if tag in ('main','article'):
            self.main_depth=max(0,self.main_depth-1)
        if tag in ('script','style','noscript','head'):
            self.skip_depth=max(0,self.skip_depth-1)
        if tag=='script' and self.buffer is not None:
            value=''.join(self.buffer)
            if len(value)<=200000 and len(self.scripts)<30:
                try:
                    self.scripts.append(json.loads(value))
                except ValueError:
                    pass
            self.buffer=None


def restricted(text):
    # Require actual caption evidence after this check; a 200 shell is not success.
    sample=text.lower()
    return any(value in sample for value in ('log in to continue','login to continue','you must log in','verify you are human',
        'captcha challenge','access denied','this content isn\'t available','content is not available','page isn\'t available'))


def walk(value,depth=0):
    if depth>12:
        return
    if isinstance(value,dict):
        yield value
        for child in list(value.values())[:100]:
            yield from walk(child,depth+1)
    elif isinstance(value,list):
        for child in value[:100]:
            yield from walk(child,depth+1)


def publication_time(value):
    try:
        stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
        if stamp.tzinfo is None or stamp.timestamp()>datetime.now(timezone.utc).timestamp()+300:
            return None
        return stamp.astimezone(timezone.utc).isoformat()
    except (AttributeError,ValueError,TypeError):
        return None

class Adapter:
    platform=''
    def parse(self,target,page):
        text=page.body.decode('utf-8',errors='replace')
        if restricted(text):
            raise AccessFailure('login_required','unauthorized')
        doc=Document(); doc.feed(text)
        if target.platform in ('instagram','facebook'):
            try:
                if normalize_target(doc.meta.get('og:url','')).url!=target.url:
                    raise ValueError()
            except ValueError:
                raise AccessFailure('invalid_content','failed') from None
        return self.content(target,doc)
    def content(self,target,doc):
        raise AccessFailure('unsupported','failed')
    def acquire(self,url,fetcher=fetch):
        target=normalize_target(url)
        if target.platform!=self.platform:
            raise AccessFailure('invalid_content','failed')
        if target.target_type=='profile':
            # Public profile enumeration has not been established as permitted/reliable.
            raise AccessFailure('unsupported','failed')
        robots_allowed(target.url,fetcher)
        page=fetch_document(target.url,fetcher)
        result=self.parse(target,page)
        return result,len(page.body)

class Instagram(Adapter):
    platform='instagram'
    def content(self,target,doc):
        value=doc.meta.get('og:description','')
        # Instagram metadata can contain likes/author without a usable caption.
        match=re.search(r'(?:Instagram:\s*|:\s*)[“"](.{10,20000})[”"]\s*$',value,re.S)
        if not match:
            raise AccessFailure('invalid_content','failed')
        return [{'source_url':target.url,'external_id':target.external_id,'caption':match[1],
                 'published_at':publication_time(doc.meta.get('article:published_time')),'adapter':'instagram_public_post_metadata_v1','content_type':'text'}]

class Facebook(Adapter):
    platform='facebook'
    def content(self,target,doc):
        caption=doc.meta.get('og:description','').strip()
        if len(caption)<20 or caption.lower() in ('log into facebook','connect with friends and the world around you on facebook.'):
            raise AccessFailure('invalid_content','failed')
        return [{'source_url':target.url,'external_id':target.external_id,'caption':caption[:20000],
                 'published_at':publication_time(doc.meta.get('article:published_time')),'adapter':'facebook_public_post_metadata_v1','content_type':'text'}]

class TikTok(Adapter):
    platform='tiktok'
    def content(self,target,doc):
        for script in doc.scripts:
            for item in walk(script):
                if str(item.get('id',''))!=target.external_id or not item.get('desc') or not item.get('createTime'):
                    continue
                author=item.get('author',{})
                handle=target.url.split('/@',1)[1].split('/',1)[0]
                if not isinstance(author,dict) or str(author.get('uniqueId','')).lower()!=handle:
                    continue
                try:
                    published=datetime.fromtimestamp(int(item['createTime']),timezone.utc).isoformat()
                except (ValueError,OverflowError,OSError):
                    continue
                return [{'source_url':target.url,'external_id':target.external_id,'caption':str(item['desc'])[:20000],
                         'published_at':published,'adapter':'tiktok_public_video_metadata_v1','content_type':'text'}]
        raise AccessFailure('invalid_content','failed')

class EventURL(Adapter):
    platform='event_url'
    def content(self,target,doc):
        from zoneinfo import ZoneInfo
        for script in doc.scripts:
            for item in walk(script):
                types=item.get('@type',[])
                types=[types] if isinstance(types,str) else types
                if not any(isinstance(t,str) and t.endswith('Event') for t in types) or not item.get('name') or not item.get('startDate'):
                    continue
                location=item.get('location',{})
                if not isinstance(location,dict):
                    continue
                raw=item['startDate']
                try:
                    date=datetime.fromisoformat(raw.replace('Z','+00:00'))
                    # Never invent a time for date-only announcements.
                    date=date.astimezone(ZoneInfo('Europe/Bratislava')).isoformat() if date.tzinfo else raw
                except (ValueError,TypeError):
                    continue
                caption='\n'.join(str(x) for x in (item['name'],item.get('description',''),date,location.get('name','')) if x)
                return [{'source_url':target.url,'external_id':target.external_id,'caption':caption[:20000],
                         'published_at':None,'adapter':'public_event_jsonld_v1','content_type':'event'}]
        title=doc.meta.get('og:title','').strip()
        body=' '.join(doc.visible).strip() or doc.meta.get('og:description','').strip()
        if title and len(body)>=40:
            return [{'source_url':target.url,'external_id':target.external_id,'caption':(title+'\n'+body)[:20000],
                     'published_at':publication_time(doc.meta.get('article:published_time')),'adapter':'public_event_page_text_v1','content_type':'text'}]
        raise AccessFailure('invalid_content','failed')

ADAPTERS={adapter.platform:adapter() for adapter in (Instagram,Facebook,TikTok,EventURL)}
