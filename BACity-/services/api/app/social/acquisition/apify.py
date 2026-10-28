"""Official selected Actor transport and provider-independent Instagram records.

No staff/database imports, cookies, log scraping, video downloads or fallbacks.
"""
from .policy import MAX_POSTS
import json
import re
import os
import time
from decimal import Decimal,InvalidOperation,ROUND_CEILING
from datetime import datetime,timezone
import httpx
from .urls import normalize_target
from .adapters import publication_time
from .scrapingant import ProviderFailure,retry_seconds,bounded_caption,media_reference

ACTOR='apify/instagram-scraper'
ACTOR_ID='shu8hvrXbJbY3Eb9W'
TERMINAL={'SUCCEEDED','FAILED','TIMED-OUT','ABORTED'}


def money(value):
    try:
        number=Decimal(str(value))
        if not number.is_finite() or not 0<=number<=1000000:raise ValueError()
        return int((number*1000000).to_integral_value(rounding=ROUND_CEILING))
    except (InvalidOperation,ValueError,TypeError):raise ProviderFailure('billing_unverified') from None


def timestamp(value):
    valid=publication_time(value)
    if not valid:raise ProviderFailure('invalid_content')
    return datetime.fromisoformat(valid).timestamp()

class Client:
    def __init__(self,token,transport=None):self.token=token;self.transport=transport;self.requests=0;self.bytes=0
    def request(self,method,path,*,params=None,body=None):
        if not self.token:raise ProviderFailure('provider_not_configured')
        allowed=(method=='GET' and path in ('/users/me/limits','/acts/apify~instagram-scraper')) or (method=='POST' and path=='/acts/apify~instagram-scraper/runs')
        allowed=allowed or bool(re.fullmatch(r'/actor-runs/[A-Za-z0-9]{1,32}'+('/abort' if method=='POST' else ''),path))
        allowed=allowed or (method=='GET' and bool(re.fullmatch(r'/datasets/[A-Za-z0-9]{1,32}(/items)?',path)))
        if not allowed:raise ProviderFailure('provider_configuration')
        proxy=os.environ.get('SOCIAL_EGRESS_PROXY')
        if proxy and proxy!='http://social-egress:3128':raise ProviderFailure('provider_configuration')
        self.requests+=1;deadline=time.monotonic()+15
        try:
            with httpx.Client(transport=self.transport,proxy=proxy if self.transport is None else None,trust_env=False,follow_redirects=False,
                timeout=httpx.Timeout(10,connect=3),limits=httpx.Limits(max_connections=1),headers={'Authorization':'Bearer '+self.token}) as client:
                with client.stream(method,'https://api.apify.com/v2'+path,params=params,json=body) as response:
                    raw=bytearray()
                    for chunk in response.iter_bytes(16384):
                        raw.extend(chunk);self.bytes+=len(chunk)
                        if len(raw)>2*1024*1024:raise ProviderFailure('response_limit')
                        if time.monotonic()>deadline:raise ProviderFailure('timeout')
                    if response.status_code==429:raise ProviderFailure('rate_limit',retry_seconds(response.headers.get('retry-after')))
                    if response.status_code in (401,403):raise ProviderFailure('provider_auth')
                    if response.status_code>=500:raise ProviderFailure('provider_transient')
                    if response.status_code not in (200,201):raise ProviderFailure('provider_denied')
                    try:data=json.loads(raw)
                    except (ValueError,RecursionError):raise ProviderFailure('invalid_content') from None
                    if self.token in json.dumps(data,ensure_ascii=False):raise ProviderFailure('invalid_content')
                    return data
        except (httpx.HTTPError,OSError):raise ProviderFailure('network_error') from None
    def preflight(self):
        account=self.request('GET','/users/me/limits')['data']
        actor=self.request('GET','/acts/apify~instagram-scraper')['data']
        return billing_snapshot(account,actor)
    def launch(self,actor_input,cap,build):
        # Intentionally no automatic POST retry: API documents no run idempotency key.
        return self.request('POST','/acts/apify~instagram-scraper/runs',params={
            'timeout':300,'memory':1024,'build':build,'maxTotalChargeUsd':str(Decimal(cap)/1000000),'restartOnError':'false'},body=actor_input)['data']
    def run(self,run_id):return self.request('GET','/actor-runs/'+run_id)['data']
    def abort(self,run_id):return self.request('POST','/actor-runs/'+run_id+'/abort')['data']
    def dataset(self,dataset_id):return self.request('GET','/datasets/'+dataset_id)['data']
    def page(self,dataset_id,offset):
        return self.request('GET','/datasets/'+dataset_id+'/items',params={'format':'json','clean':'true','offset':offset,'limit':5})


def billing_snapshot(account,actor):
    try:
        if actor['id']!=ACTOR_ID or actor['username']!='apify' or actor['name']!='instagram-scraper':raise ValueError()
        cycle=account['monthlyUsageCycle'];start=timestamp(cycle['startAt'])
        end=datetime.fromisoformat(cycle['endAt'].replace('Z','+00:00')).timestamp()
        if not start<=time.time()<end or end-start>40*86400:raise ValueError()
        usage=money(account['current']['monthlyUsageUsd']);limit=money(account['limits']['maxMonthlyUsageUsd'])
        pricing=max((p for p in actor['pricingInfos'] if timestamp(p['startedAt'])<=time.time()),key=lambda p:p['startedAt'])
        if pricing['pricingModel']!='PAY_PER_EVENT':raise ValueError()
        events=pricing['pricingPerEvent']['actorChargeEvents']
        if set(events)-{'result','actor-start'}:raise ValueError()
        price=money(events['result']['eventTieredPricingUsd']['FREE']['tieredEventPriceUsd'])
        startup=money(events['actor-start']['eventTieredPricingUsd']['FREE']['tieredEventPriceUsd']) if 'actor-start' in events else 0
        build=actor['taggedBuilds']['latest']['buildNumber']
        if not re.fullmatch(r'\d+\.\d+\.\d+',build) or price<=0:raise ValueError()
        return {'start':start,'end':end,'used':usage,'limit':min(limit,5000000),'price':price,'startup':startup,'build':build}
    except (KeyError,TypeError,ValueError):raise ProviderFailure('billing_unverified') from None


def actor_input(members,limit):
    limit=min(MAX_POSTS,limit)
    value={'directUrls':[m['url'] for m in members],'resultsType':'posts','resultsLimit':limit,'addParentData':True,
           'skipPinnedPosts':True} # README documents this; generated OpenAPI currently omits it.
    stamps=[m.get('checkpoint_timestamp') for m in members]
    if stamps and all(stamps):
        value['onlyPostsNewerThan']=datetime.fromtimestamp(min(stamps)-1,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return value


def normalize_record(record,members):
    """Never infer attribution from batch order or use engagement/video payloads."""
    if not isinstance(record,dict):raise ProviderFailure('invalid_content')
    handles={m['handle']:m for m in members}
    source=record.get('inputUrl')
    source_handle=None
    if isinstance(source,str):
        try:
            parsed=normalize_target(source)
            if parsed.platform=='instagram' and parsed.target_type=='profile':source_handle=parsed.external_id
        except ValueError:pass
    owner=record.get('ownerUsername')
    owner=owner.lower() if isinstance(owner,str) else None
    if owner and source_handle and owner!=source_handle:raise ProviderFailure('invalid_content')
    handle=owner or source_handle
    if handle not in handles:raise ProviderFailure('invalid_content')
    member=handles[handle]
    if record.get('error'):
        text=str(record.get('error'))+' '+str(record.get('errorDescription',''))
        text=text.lower()
        error='challenge' if 'captcha' in text or 'challenge' in text else 'login_required' if 'login' in text or 'log in' in text else 'access_denied' if 'private' in text or 'denied' in text or 'restricted' in text else 'unavailable_content'
        return member['job_id'],None,error
    if not owner:raise ProviderFailure('invalid_content')
    if record.get('type') not in ('Image','Video','Sidecar'):raise ProviderFailure('invalid_content')
    code=record.get('shortCode');url=record.get('url')
    if not isinstance(code,str) or not isinstance(url,str):raise ProviderFailure('invalid_content')
    try:target=normalize_target(url)
    except ValueError:raise ProviderFailure('invalid_content') from None
    if target.platform!='instagram' or target.target_type!='post' or target.external_id!=code:raise ProviderFailure('invalid_content')
    published=publication_time(record.get('timestamp'))
    if not published:raise ProviderFailure('invalid_content') # No newest-item claim without time.
    stamp=datetime.fromisoformat(published).timestamp()
    if member.get('checkpoint_timestamp') and stamp<member['checkpoint_timestamp']:return member['job_id'],None,'older_item_skipped'
    if record.get('isPinned') and stamp<time.time()-86400:return member['job_id'],None,'pinned_item_skipped'
    reel=record.get('productType')=='clips' or '/reel/' in target.url
    source_url=f'https://www.instagram.com/{"reel" if reel else "p"}/{code}/'
    caption=bounded_caption(record.get('caption','')) if isinstance(record.get('caption',''),str) else ''
    media=[]
    for child in [record]+(record.get('childPosts',[]) if isinstance(record.get('childPosts',[]),list) else [])[:3]:
        if isinstance(child,dict):
            reference=media_reference(child.get('displayUrl'))
            if reference and reference not in media:media.append(reference)
    return member['job_id'],{'source_url':source_url,'external_id':code,'caption':caption,'published_at':published,
        'publisher_identifier':handle,'content_type':'text','adapter':'apify_instagram_v1','media':media[:3]},None
