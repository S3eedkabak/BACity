"""Reject private destinations, including redirects; respect robots crawl delays."""
import ipaddress
import socket
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from scrapy.exceptions import IgnoreRequest
from twisted.internet.threads import deferToThread
from scrapy.utils.defer import maybe_deferred_to_future
from scrapy.resolver import dnscache


class PublicNetworkMiddleware:
    def __init__(self):
        self.delays = {}

    def apply_delay(self, request, spider):
        host = urlsplit(request.url).hostname
        delay = self.delays.get(host)
        if delay:
            request.meta['autothrottle_dont_adjust_delay'] = True
            slot = spider.crawler.engine.downloader.slots.get(request.meta.get('download_slot', host))
            if slot:
                slot.delay = max(slot.delay, delay)

    async def process_request(self, request, spider):
        import os
        if request.meta.get('playwright') and os.getenv('CRAWLER_RENDER_NETWORK_ISOLATED') != '1':
            raise IgnoreRequest('Rendering requires operator-verified public-only network isolation')
        from crawler.spiders.discovery import allowed_url
        try:
            if not allowed_url(request.url):
                raise IgnoreRequest('URL denied by crawl policy')
        except ValueError:
            raise IgnoreRequest('Malformed URL')
        self.apply_delay(request, spider)

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
        await maybe_deferred_to_future(deferToThread(check))

    def process_response(self, request, response, spider):
        delay = None
        if urlsplit(request.url).path == '/robots.txt' and response.status == 200:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            delay = parser.crawl_delay(spider.settings.get('USER_AGENT')) or parser.crawl_delay('*')
        if response.status in (429, 503):
            try:
                delay = min(float(response.headers.get('Retry-After', b'60')), 3600)
            except ValueError:
                delay = 60
        if delay:
            host = urlsplit(request.url).hostname
            self.delays[host] = max(self.delays.get(host, 0), delay)
        self.apply_delay(request, spider)
        return response
