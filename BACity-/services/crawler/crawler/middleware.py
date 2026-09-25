"""Reject private destinations, including redirects; respect robots crawl delays."""
import ipaddress
import socket
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from scrapy.exceptions import IgnoreRequest
from twisted.internet.threads import deferToThread


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

    def process_request(self, request, spider):
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
        return deferToThread(check)

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
