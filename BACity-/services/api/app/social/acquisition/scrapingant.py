"""Replaceable provider transport/parser. No ORM, staff secrets or ingestion.

No cookies, browser rendering, residential upgrades, challenge solving or retries.
All network calls, including account-status calls, require a quota callback first.
"""
import json
import time
import uuid
import re
import os
from datetime import datetime,timezone
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
import httpx
from .urls import normalize_target
from .adapters import restricted,publication_time

MAX_BYTES=2*1024*1024

class ProviderFailure(Exception):
    def __init__(self,category,retry_after=0):
        self.category=category;self.retry_after=retry_after
        super().__init__(category)  # Never retain response text, request objects or keys.

class Client:
    def __init__(self,key,transport=None):
        self.key=key;self.transport=transport;self.bytes=0
    def request(self,kind,target=None):
        if not self.key:raise ProviderFailure('provider_not_configured')
        proxy=os.environ.get('SOCIAL_EGRESS_PROXY')
        if proxy and proxy!='http://social-egress:3128':raise ProviderFailure('provider_configuration')
        params={} if kind=='usage' else {'url':normalize_target(target).url,'browser':'false','proxy_type':'datacenter','timeout':'5'}
        cost=None;deadline=time.monotonic()+10
        try:
            with httpx.Client(transport=self.transport,proxy=proxy if self.transport is None else None,trust_env=False,follow_redirects=False,
                              timeout=httpx.Timeout(8,connect=3),limits=httpx.Limits(max_connections=1),headers={'x-api-key':self.key,'Accept':'application/json'}) as client:
                with client.stream('GET','https://api.scrapingant.com/v2/'+('usage' if kind=='usage' else 'extended'),params=params) as response:
                    value=response.headers.get('ant-credits-cost')
                    if value is not None and re.fullmatch(r'\d{1,7}',value):cost=int(value)
                    retry=retry_seconds(response.headers.get('retry-after'))
                    body=bytearray()
                    for chunk in response.iter_bytes(16384):
                        body.extend(chunk);self.bytes+=len(chunk)
                        if len(body)>MAX_BYTES:raise ProviderFailure('response_limit')
                        if time.monotonic()>deadline:raise ProviderFailure('timeout')
                    if response.status_code==429:raise ProviderFailure('rate_limit',retry)
                    if response.status_code==403:raise ProviderFailure('provider_auth')
                    if response.status_code in (401,423):raise ProviderFailure('provider_denied')
                    if response.status_code in (404,409) or response.status_code>=500:raise ProviderFailure('provider_transient',retry)
                    if response.status_code!=200:raise ProviderFailure('provider_denied')
                    try:data=json.loads(body)
                    except (ValueError,RecursionError):raise ProviderFailure('invalid_content') from None
                    if not isinstance(data,dict) or self.key in json.dumps(data,ensure_ascii=False):raise ProviderFailure('invalid_content')
                    return data,cost
        except ProviderFailure as exc:
            exc.cost=cost;raise
        except (httpx.HTTPError,OSError,ValueError):
            failure=ProviderFailure('network_error');failure.cost=cost;raise failure from None


def retry_seconds(value):
    if not value:return 0
    try:return min(604800,max(0,int(value)))
    except ValueError:
        from email.utils import parsedate_to_datetime
        try:return min(604800,max(0,int(parsedate_to_datetime(value).timestamp()-time.time())))
        except (ValueError,TypeError,OverflowError):return 0


def usage_snapshot(data):
    try:
        def stamp(key):
            value=datetime.fromisoformat(data[key].replace('Z','+00:00'))
            # Provider documents naive ISO subscription dates; interpret them as UTC.
            return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()
        total,remaining=data['plan_total_credits'],data['remained_credits']
        if type(total) is not int or type(remaining) is not int or not 0<=remaining<=total<=1000000000:raise ValueError()
        start,end=stamp('start_date'),stamp('end_date')
        if not start<=time.time()+300<end or end-start>370*86400:raise ValueError()
        return {'start':start,'end':end,'total':total,'remaining':remaining}
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
        raise ProviderFailure('usage_unverified') from None

class ProfileDocument(HTMLParser):
    def __init__(self):
        super().__init__();self.meta={};self.scripts=[];self.links=[];self.parts=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='meta':self.meta[attrs.get('property') or attrs.get('name')]=attrs.get('content','')[:30000]
        if tag=='a' and len(self.links)<200:self.links.append(attrs.get('href',''))
        if tag=='script':self.parts=[]
    def handle_data(self,value):
        if self.parts is not None:self.parts.append(value)
    def handle_endtag(self,tag):
        if tag=='script' and self.parts is not None:
            raw=''.join(self.parts).strip();self.parts=None
            if len(raw)>MAX_BYTES or len(self.scripts)>=40:return
            if raw.startswith('window._sharedData = '):raw=raw[len('window._sharedData = '):].rstrip(';')
            try:self.scripts.append(json.loads(raw))
            except (ValueError,RecursionError):pass


def bounded_caption(value):
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f]','',value).encode('utf-8')[:3500].decode('utf-8','ignore')


def media_reference(value):
    if not isinstance(value,str) or len(value)>1500:return None
    try:
        p=urlsplit(value);host=p.hostname or ''
        if p.scheme=='https' and not p.username and not p.password and p.port in (None,443) and (host.endswith('.cdninstagram.com') or host.endswith('.fbcdn.net')):
            # Reference only: no download, no video, no HTML rendering in the panel.
            return value
    except ValueError:pass
    return None


def parse_document(url,data,expected_handle):
    target=normalize_target(url)
    if target.platform!='instagram':raise ProviderFailure('invalid_content')
    status=data.get('status_code')
    if status in (401,403):raise ProviderFailure('access_denied')
    if status==429:raise ProviderFailure('rate_limit')
    if status!=200:raise ProviderFailure('unavailable_content' if status==404 else 'invalid_content')
    html=data.get('html',data.get('content'))
    if not isinstance(html,str) or not html or len(html.encode())>MAX_BYTES:raise ProviderFailure('invalid_content')
    visible=html.lower()
    if any(x in visible for x in ('verify you are human','captcha challenge','challenge_required','checkpoint_required','/challenge/')):
        raise ProviderFailure('challenge')
    if 'access denied' in visible:raise ProviderFailure('access_denied')
    if any(x in visible for x in ("this content isn't available",'content is not available',"page isn't available")):raise ProviderFailure('unavailable_content')
    if restricted(html) or re.search(r'<form[^>]+(?:action=["\'][^"\']*(?:accounts/login|/login))',html,re.I):
        raise ProviderFailure('login_required')
    doc=ProfileDocument();doc.feed(html)
    posts={};identified=False;profile_verified=False;private=False;visited=0
    def walk(value,owner=None,depth=0):
        nonlocal identified,profile_verified,private,visited
        visited+=1
        if depth>24 or visited>30000:return
        if isinstance(value,list):
            for child in value[:100]:walk(child,owner,depth+1)
        elif isinstance(value,dict):
            username=value.get('username')
            if isinstance(username,str):
                owner=username.lower()
                if owner==expected_handle:
                    identified=True;private=private or value.get('is_private') is True
                    profile_verified=profile_verified or any(k in value for k in ('edge_owner_to_timeline_media','edge_felix_video_timeline','media_count','is_private'))
            direct_owner=value.get('owner') or value.get('user')
            if isinstance(direct_owner,dict) and isinstance(direct_owner.get('username'),str):owner=direct_owner['username'].lower()
            code=value.get('shortcode') or value.get('code')
            if owner==expected_handle and isinstance(code,str) and re.fullmatch(r'[A-Za-z0-9_-]{3,100}',code):
                is_reel=value.get('product_type')=='clips' or '/reel/' in str(value.get('permalink',''))
                source=f'https://www.instagram.com/{"reel" if is_reel else "p"}/{code}/'
                if target.target_type=='post' and code!=target.external_id:return
                caption=value.get('caption')
                if isinstance(caption,dict):caption=caption.get('text')
                if not isinstance(caption,str):
                    edges=value.get('edge_media_to_caption',{}).get('edges',[]) if isinstance(value.get('edge_media_to_caption',{}),dict) else []
                    caption=next((e.get('node',{}).get('text') for e in edges[:3] if isinstance(e,dict)),None)
                published=None;stamp=value.get('taken_at_timestamp',value.get('taken_at'))
                if isinstance(stamp,(int,float)) and not isinstance(stamp,bool) and 0<stamp<=time.time()+300:
                    try:published=datetime.fromtimestamp(stamp,timezone.utc).isoformat()
                    except (ValueError,OverflowError,OSError):pass
                media=media_reference(value.get('display_url') or value.get('thumbnail_src'))
                images=value.get('image_versions2',{})
                if not media and isinstance(images,dict):
                    candidates=images.get('candidates',[])
                    if isinstance(candidates,list):
                        media=next((m for image in candidates[:3] if isinstance(image,dict) and (m:=media_reference(image.get('url')))),None)
                posts[code]={'source_url':source,'external_id':code,'caption':bounded_caption(caption) if isinstance(caption,str) else '',
                    'published_at':published,'content_type':'text','adapter':'scrapingant_instagram_v1','publisher_identifier':expected_handle,
                    'media':[media] if media else [],'is_reel':is_reel}
            for child in list(value.values())[:200]:walk(child,owner,depth+1)
    for script in doc.scripts:walk(script)
    try:canonical=normalize_target(doc.meta.get('og:url','')).url==target.url
    except ValueError:canonical=False
    if doc.meta.get('og:url') and not canonical:raise ProviderFailure('invalid_content')
    if target.target_type=='profile' and not (canonical or profile_verified):raise ProviderFailure('invalid_content')
    if private:raise ProviderFailure('access_denied')
    if not identified and not canonical:raise ProviderFailure('invalid_content')
    # An empty shell is never classified as a successfully acquired profile.
    if not identified and not posts and not doc.links:raise ProviderFailure('invalid_content')
    links=[]
    for href in doc.links:
        try:
            link=normalize_target(urljoin(target.url,href))
            if link.platform=='instagram' and link.target_type=='post' and link.url not in links:links.append(link.url)
        except ValueError:pass
    # Direct public post metadata fallback requires exact canonical URL and author evidence.
    if target.target_type=='post' and not posts and canonical:
        author=doc.meta.get('instapp:owner_user_name')
        caption=doc.meta.get('og:description','')
        if author and author.lower()==expected_handle and len(caption)>=5:
            posts[target.external_id]={'source_url':target.url,'external_id':target.external_id,'caption':bounded_caption(caption),
                'published_at':publication_time(doc.meta.get('article:published_time')),'content_type':'text',
                'adapter':'scrapingant_instagram_v1','publisher_identifier':expected_handle,'media':[], 'is_reel':'/reel/' in target.url}
    has_empty_feed=any(x in html for x in ('edge_owner_to_timeline_media','xdt_api__v1__feed__user_timeline_graphql_connection'))
    if not posts and not links and not (identified and has_empty_feed):raise ProviderFailure('invalid_content')
    return list(posts.values())[:20],links[:20]


def collect(job,client,quota,*,request_id_factory=None):
    """quota(action, payload) reserves/settles with the existing private gateway."""
    started=time.monotonic();requests=0;credits=0;estimated=0
    observations=[];discovered={};links=[];error=None;retry=0
    def request(kind,url=None):
        nonlocal requests,credits,estimated
        if time.monotonic()-started>50:raise ProviderFailure('timeout')
        reservation=str(request_id_factory() if request_id_factory else uuid.uuid4())
        quota('reserve',{'request_id':reservation,'kind':kind,'target':url or ''})
        requests+=1;cost=None;failure=None;snapshot=None
        try:
            data,cost=client.request(kind,url)
            if kind=='usage':snapshot=usage_snapshot(data)
            return data
        except ProviderFailure as exc:
            cost=getattr(exc,'cost',cost);failure=exc.category;raise
        finally:
            settled=quota('settle',{'request_id':reservation,'cost':cost,'snapshot':snapshot,'error':failure})
            credits+=settled.get('cost',125)
            estimated+=int(settled.get('cost_kind')=='estimated')
    try:
        health=quota('status',{})
        if health['needs_sync'] or health['suspension_reason'] not in (None,'budget_exhausted'):
            request('usage')
        handle=normalize_target(job['url']).external_id
        page=request('acquire',job['url'])
        posts,links=parse_document(job['url'],page,handle)
        discovered.update({p['external_id']:p for p in posts})
        # At most two additional direct documents, sharing the same quota and job.
        pending=[p['source_url'] for p in posts if len(p['caption'])<5]+links
        for url in dict.fromkeys(pending):
            if requests>=4 or len([p for p in discovered.values() if len(p['caption'])>=5])>=5:break
            more,_=parse_document(url,request('acquire',url),handle)
            discovered.update({p['external_id']:p for p in more})
    except ProviderFailure as exc:error=exc.category;retry=exc.retry_after
    observations=[p for p in discovered.values() if len(p['caption'])>=5][:5]
    # Quota errors must be sanitized by the gateway callback, never echoed HTTP bodies.
    for post in observations:post.pop('is_reel',None)
    restricted_error=error in ('login_required','challenge','access_denied','provider_denied','provider_auth')
    if restricted_error:observations=[]
    outcome=('unauthorized' if error=='login_required' else 'blocked') if restricted_error else 'rate_limited' if error=='rate_limit' else 'partial' if error and observations else 'failed' if error else 'success' if observations else 'empty'
    return {'outcome':outcome,'error':error or 'none','observations':observations,'retry_after':retry,
        'requests':requests,'bytes_received':client.bytes,'elapsed_ms':min(60000,int((time.monotonic()-started)*1000)),
        'provider_metrics':{'posts_discovered':len(discovered),'reels_discovered':sum('/reel/' in p['source_url'] for p in discovered.values()),
            'captions_available':sum(len(p['caption'])>=5 for p in discovered.values()),'dates_available':sum(bool(p['published_at']) for p in discovered.values()),
            'media_available':sum(bool(p['media']) for p in discovered.values()),'credits_accounted':credits,'estimated_requests':estimated}}
