"""Small HTTPS client with public-IP pinning and an optional restricted CONNECT proxy."""
import http.client
import ipaddress
import os
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
from .urls import EVENT_HOSTS

USER_AGENT='BACityBot/1.0 (+https://github.com/S3eedkabak/BACity)'
HOSTS=frozenset({'instagram.com','www.instagram.com','facebook.com','www.facebook.com','tiktok.com','www.tiktok.com',*EVENT_HOSTS,
                 *('www.'+x for x in EVENT_HOSTS)})
MAX_BYTES=2*1024*1024

class AccessFailure(Exception):
    def __init__(self,category,outcome='blocked',retry_after=0):
        super().__init__(category)
        self.category,self.outcome,self.retry_after=category,outcome,retry_after

@dataclass
class Page:
    url: str
    status: int
    body: bytes
    headers: dict


def public_addresses(host):
    try:
        addresses=list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    except OSError:
        raise AccessFailure('network_error','failed') from None
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise AccessFailure('access_denied')
    return addresses


def checked_url(url):
    if len(url)>2048 or '\\' in url or any(ord(x)<32 for x in url):
        raise AccessFailure('access_denied')
    try:
        p=urlsplit(url)
        if p.scheme!='https' or p.hostname not in HOSTS or p.username or p.password or p.port not in (None,443):
            raise AccessFailure('access_denied')
    except ValueError:
        raise AccessFailure('access_denied') from None
    return p


class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        # Resolve once and connect to that exact public address; TLS still checks host.
        address=public_addresses(self.host)[0]
        raw=socket.create_connection((address,self.port),self.timeout)
        try:
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException:
            raw.close(); raise


def fetch(url,*,max_bytes=MAX_BYTES,timeout=10):
    parsed=checked_url(url)
    proxy=os.getenv('SOCIAL_EGRESS_PROXY','')
    if proxy:
        p=urlsplit(proxy)
        # Deployment configuration only, never derived from a job or publisher.
        if p.scheme!='http' or p.hostname!='social-egress' or p.port!=3128:
            raise AccessFailure('access_denied')
        connection=http.client.HTTPSConnection(p.hostname,p.port,timeout=timeout,context=ssl.create_default_context())
        connection.set_tunnel(parsed.hostname,443)
    else:
        connection=PinnedHTTPS(parsed.hostname,443,timeout=timeout,context=ssl.create_default_context())
    try:
        path=parsed.path or '/'
        if parsed.query:
            path+='?'+parsed.query
        connection.request('GET',path,headers={'User-Agent':USER_AGENT,'Accept':'text/html,application/json,text/plain;q=0.8','Accept-Encoding':'identity'})
        response=connection.getresponse()
        headers={key.lower():value for key,value in response.getheaders()}
        if response.status in (401,403,429):
            retry=0
            if response.status==429:
                from email.utils import parsedate_to_datetime
                value=headers.get('retry-after','60')
                try:
                    retry=int(value) if value.isdigit() else int(parsedate_to_datetime(value).timestamp()-time.time())
                except (ValueError,TypeError):
                    retry=60
            raise AccessFailure('rate_limit' if response.status==429 else 'login_required' if response.status==401 else 'access_denied',
                                'rate_limited' if response.status==429 else 'unauthorized' if response.status==401 else 'blocked',max(0,min(604800,retry)))
        if headers.get('content-encoding','identity').lower() not in ('identity',''):
            raise AccessFailure('invalid_content','failed')
        length=headers.get('content-length','')
        if length.isdigit() and int(length)>max_bytes:
            raise AccessFailure('response_limit','failed')
        chunks=[]; size=0; deadline=time.monotonic()+min(timeout,20)
        while True:
            if time.monotonic()>deadline:
                raise AccessFailure('timeout','failed')
            chunk=response.read(min(65536,max_bytes-size+1))
            if not chunk:
                break
            size+=len(chunk)
            if size>max_bytes:
                raise AccessFailure('response_limit','failed')
            chunks.append(chunk)
        return Page(url,response.status,b''.join(chunks),headers)
    except (socket.timeout,TimeoutError):
        raise AccessFailure('timeout','failed') from None
    except (OSError,http.client.HTTPException):
        raise AccessFailure('network_error','failed') from None
    finally:
        connection.close()


def robots_allowed(url,fetcher=fetch):
    p=checked_url(url)
    page=fetcher(f'https://{p.netloc}/robots.txt',max_bytes=256*1024)
    if page.status not in (200,404):
        raise AccessFailure('robots_denied')
    if page.status==404:
        return
    parser=RobotFileParser()
    parser.parse(page.body.decode('utf-8',errors='replace').splitlines())
    if not parser.can_fetch(USER_AGENT,url):
        raise AccessFailure('robots_denied')
    delay=parser.crawl_delay(USER_AGENT) or parser.crawl_delay('*') or 0
    if delay>10:
        raise AccessFailure('robots_denied')
    if delay:
        time.sleep(delay)


def fetch_document(url,fetcher=fetch):
    original=checked_url(url)
    for _ in range(3):
        page=fetcher(url)
        if page.status in (301,302,303,307,308):
            next_url=urljoin(url,page.headers.get('location',''))
            p=checked_url(next_url)
            if p.hostname.removeprefix('www.')!=original.hostname.removeprefix('www.'):
                raise AccessFailure('access_denied')
            if any(word in p.path.lower() for word in ('/login','/accounts/','/challenge','/checkpoint')):
                raise AccessFailure('login_required','unauthorized')
            robots_allowed(next_url,fetcher)
            url=next_url
            continue
        if page.status!=200:
            raise AccessFailure('invalid_content','failed')
        if not any(kind in page.headers.get('content-type','') for kind in ('text/html','application/json')):
            raise AccessFailure('invalid_content','failed')
        return page
    raise AccessFailure('access_denied')


class NetworkBudget:
    """One transparent request at a time; aggregate byte/request/deadline limits."""
    def __init__(self,fetcher=fetch):
        import threading
        self.fetcher=fetcher
        self.lock=threading.Lock()
        self.requests=0
        self.received=0
        self.deadline=time.monotonic()+35
        self.restricted=None
    def __call__(self,url,**kwargs):
        with self.lock:
            if self.restricted:
                raise self.restricted
            if self.requests>=12 or self.received>=4*1024*1024:
                raise AccessFailure('response_limit','failed')
            if time.monotonic()>=self.deadline:
                raise AccessFailure('timeout','failed')
            self.requests+=1
            kwargs['max_bytes']=min(kwargs.get('max_bytes',MAX_BYTES),4*1024*1024-self.received)
            kwargs['timeout']=max(0.1,min(kwargs.get('timeout',10),self.deadline-time.monotonic()))
            try:
                page=self.fetcher(url,**kwargs)
            except AccessFailure as failure:
                if failure.outcome in ('blocked','unauthorized','rate_limited'):
                    self.restricted=failure
                raise
            self.received+=len(page.body)
            return page
