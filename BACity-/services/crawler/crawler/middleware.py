"""Reject private destinations, including redirects; respect robots crawl delays."""
import ipaddress
import socket
import time
import asyncio
from crawler.retry import retry_after
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from scrapy.exceptions import IgnoreRequest
from twisted.internet.threads import deferToThread
from scrapy.utils.defer import maybe_deferred_to_future
from scrapy.resolver import dnscache


class PublicNetworkMiddleware:
    def __init__(self):
        self.delays = {}
        self.retry_until = {}
        self.public_addresses = {}

    @classmethod
    def from_crawler(cls, crawler):
        instance = cls()
        instance.crawler = crawler
        return instance

    def apply_delay(self, request, spider):
        host = urlsplit(request.url).hostname
        delay = self.delays.get(host)
        if delay:
            request.meta['autothrottle_dont_adjust_delay'] = True
            slot = spider.crawler.engine.downloader.slots.get(request.meta.get('download_slot', host))
            if slot:
                slot.delay = max(slot.delay, delay)

    async def process_request(self, request, spider=None):
        spider = spider or self.crawler.spider
        import os
        if request.meta.get('playwright') and os.getenv('CRAWLER_RENDER_NETWORK_ISOLATED') != '1':
            raise IgnoreRequest('Rendering requires operator-verified public-only network isolation')
        from crawler.spiders.discovery import allowed_url
        try:
            if not allowed_url(request.url):
                raise IgnoreRequest('URL denied by crawl policy')
        except ValueError:
            raise IgnoreRequest('Malformed URL')
        host=urlsplit(request.url).hostname
        remaining=self.retry_until.get(host,0)-time.time()
        if remaining>30:
            # Persisted stats tell the scheduler when the publisher allows a
            # retry. Do not spend the entire crawl budget holding a connection.
            raise IgnoreRequest('Publisher Retry-After deferred to scheduler')
        if remaining>0:
            await asyncio.sleep(remaining)
        self.apply_delay(request, spider)
        cached=self.public_addresses.get(host)
        if cached and cached[0]>time.monotonic() and not request.meta.get('redirect_times'):
            # Reuse only a previously validated public address and re-pin the
            # actual connection. A DNS change cannot redirect this cached
            # connection into a private network. Redirects always revalidate.
            dnscache[host]=cached[1]
            return

        def check():
            host = urlsplit(request.url).hostname
            addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(addr[4][0]).is_global for addr in addresses):
                raise IgnoreRequest('Non-public destination')
            # Pin Scrapy's actual HTTP resolver to the already-validated address,
            # rather than checking DNS then resolving a second time on connect.
            ipv4 = next((addr[4][0] for addr in addresses if addr[0] == socket.AF_INET), None)
            if not ipv4:
                raise IgnoreRequest('No supported public IPv4 destination')
            dnscache[host] = ipv4
            if len(self.public_addresses)>=256:
                self.public_addresses.pop(next(iter(self.public_addresses)),None)
            self.public_addresses[host]=(time.monotonic()+300,ipv4)
        await maybe_deferred_to_future(deferToThread(check))

    def process_response(self, request, response, spider=None):
        spider = spider or self.crawler.spider
        delay = None
        if urlsplit(request.url).path == '/robots.txt' and response.status == 200:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            delay = parser.crawl_delay(spider.settings.get('USER_AGENT')) or parser.crawl_delay('*')
        if response.status in (429, 503):
            host=urlsplit(request.url).hostname
            until=time.time()+retry_after(response.headers.get('Retry-After',b'60'))
            self.retry_until[host]=max(self.retry_until.get(host,0),until)
            stats=spider.crawler.stats
            stats.set_value('source/retry_after_until',max(stats.get_value('source/retry_after_until',0),until))
        if delay:
            host = urlsplit(request.url).hostname
            self.delays[host] = max(self.delays.get(host, 0), delay)
        self.apply_delay(request, spider)
        return response
