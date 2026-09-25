"""Bounded, recurring event discovery from trusted sites to new public domains."""
import os
from urllib.parse import urlsplit

import scrapy
from crawler.sources import EVENT_LINK_HINTS, SourceSeed
from crawler.state import State
from crawler.spiders.bratislava_sources_spider import BratislavaSourcesSpider


def domain_matches(host, domain):
    return host == domain or host.endswith('.' + domain)


def allowed_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('http', 'https') or not host or parsed.username or parsed.password:
        return False
    if parsed.port not in (None, 80, 443):
        return False
    blocked = os.getenv('CRAWLER_BLOCK_DOMAINS', 'facebook.com,instagram.com,twitter.com,x.com,youtube.com').split(',')
    allowed = [d.strip() for d in os.getenv('CRAWLER_ALLOW_DOMAINS', '').split(',') if d.strip()]
    return not any(domain_matches(host, d.strip()) for d in blocked if d.strip()) and (
        not allowed or any(domain_matches(host, d) for d in allowed))


class DiscoverySpider(BratislavaSourcesSpider):
    name = 'discovery'
    allowed_domains = []  # Domain policy + public-address middleware replaces OffsiteMiddleware.
    custom_settings = {'CLOSESPIDER_PAGECOUNT': 150, 'CLOSESPIDER_TIMEOUT': 600}

    def __init__(self, source=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sources = [source] if source else self.sources
        self.max_crawl_depth = int(os.getenv('CRAWLER_MAX_DEPTH', '3'))
        self.max_links_per_page = int(os.getenv('CRAWLER_MAX_LINKS', '50'))
        self.source_counts = {s.name: 0 for s in self.sources}
        self.discovered = 0
        self.state = None

    def start_requests(self):
        for request in super().start_requests():
            source = request.meta['source']
            if request.url.rstrip('/') == source.base_url.rstrip('/') and source.event_url.rstrip('/') != source.base_url.rstrip('/'):
                continue
            yield request

    def parse(self, response):
        if not hasattr(response, 'text'):
            return
        source = response.meta['source']
        depth = response.meta.get('crawl_depth', 0)
        yield from self._extract(response, source)
        if depth >= self.max_crawl_depth:
            return
        followed = 0
        seen = {response.url}
        for anchor in response.css('a[href], link[rel="next"], [data-next-url], [data-load-more-url]'):
            href = anchor.attrib.get('href') or anchor.attrib.get('data-next-url') or anchor.attrib.get('data-load-more-url')
            label = anchor.xpath('string(.)').get('')
            url = response.urljoin(href).split('#', 1)[0]
            if url in seen:
                continue
            seen.add(url)
            try:
                if not allowed_url(url):
                    continue
            except ValueError:
                continue
            hint = (url + ' ' + label).lower()
            pagination = anchor.attrib.get('rel') == 'next' or any(x in hint for x in ('page=', '/page/', 'load more', 'ďalšie', 'next')) or 'data-next-url' in anchor.attrib or 'data-load-more-url' in anchor.attrib
            if not pagination and not any(word in hint for word in EVENT_LINK_HINTS):
                continue
            host = urlsplit(url).hostname.lower()
            if domain_matches(host, source.domain) and source.domain == 'visitbratislava.com' and not urlsplit(url).path.startswith('/events/'):
                continue
            if not domain_matches(host, source.domain):
                if self.discovered >= int(os.getenv('CRAWLER_MAX_NEW_SOURCES', '20')):
                    continue
                # Only expand one trust hop. Newly found sources must first prove useful;
                # they can be promoted to trusted seeds explicitly after inspection.
                from crawler.sources import ACTIVE_SOURCES
                if source.domain not in {s.domain for s in ACTIVE_SOURCES}:
                    continue
                if self.state is None:
                    self.state = State()
                if self.state.db.execute('SELECT count(*) FROM sources').fetchone()[0] >= int(os.getenv('CRAWLER_MAX_SOURCES', '250')):
                    continue
                self.state.seed(SourceSeed(host, host, f'{urlsplit(url).scheme}://{host}', url,
                                           'event_platform', 0.6, crawl_frequency_minutes=1440), response.url)
                self.discovered += 1
                self.crawler.stats.inc_value('discovery/sources')
                continue
            yield scrapy.Request(url, callback=self.parse, errback=self.errback_source,
                                 meta={'source': source, 'crawl_depth': depth + 1})
            followed += 1
            if followed >= self.max_links_per_page:
                break

    def closed(self, reason):
        self.logger.info('SOURCE_COUNTS=%s', self.source_counts)
        if self.state:
            self.state.close()
