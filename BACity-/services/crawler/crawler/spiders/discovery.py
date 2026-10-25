"""Bounded, recurring event discovery from trusted sites to new public domains."""
import os
import re
from urllib.parse import urlsplit

import scrapy
from crawler.sources import EVENT_LINK_HINTS, SourceSeed
from crawler.state import State
from crawler.spiders.bratislava_sources_spider import BratislavaSourcesSpider


def domain_matches(host, domain):
    return host == domain or host.endswith('.' + domain)


def allowed_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower().rstrip('.')
    if parsed.scheme not in ('http', 'https') or not host or parsed.username or parsed.password:
        return False
    if '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
        return False
    if parsed.port not in (None, 80, 443):
        return False
    if re.search(r'\.(?:jpe?g|png|gif|svg|webp|ico|pdf|zip|mp[34]|woff2?)$',parsed.path,re.I):
        return False
    if host in ('google.com','www.google.com','calendar.google.com') and not parsed.path.startswith('/calendar/ical/'):
        return False  # Add-to-calendar templates and search are not event sources.
    blocked = ['facebook.com', 'fb.com', 'instagram.com', 'tiktok.com', 'twitter.com', 'x.com', 'youtube.com', 'youtu.be']
    blocked += os.getenv('CRAWLER_BLOCK_DOMAINS', '').split(',')
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
        self.max_crawl_depth = min(3,max(0,int(os.getenv('CRAWLER_MAX_DEPTH', '3'))))
        self.max_links_per_page = min(50,max(1,int(os.getenv('CRAWLER_MAX_LINKS', '50'))))
        self.source_counts = {s.name: 0 for s in self.sources}
        self.discovered = 0
        self.state = None

    def _initial_requests(self):
        for request in self._source_requests():
            source = request.meta['source']
            if request.url.rstrip('/') == source.base_url.rstrip('/') and source.event_url.rstrip('/') != source.base_url.rstrip('/'):
                continue
            yield request

    async def start(self):
        for request in self._initial_requests():
            yield request

    def start_requests(self):
        # Scrapy <2.13 compatibility; modern Scrapy uses async start above.
        yield from self._initial_requests()

    def parse(self, response):
        if not hasattr(response, 'text'):
            return
        source = response.meta['source']
        depth = response.meta.get('crawl_depth', 0)
        yield from self._extract(response, source)
        if not response.text.lstrip().startswith('<'):
            return
        self._observe_instagram_profiles(response, source)
        if source.parser == 'karlova_ves_api' or response.selector.type in ('json','xml'):
            return  # Structured endpoints are data, not HTML link graphs.
        followed = 0
        seen = {response.url}
        anchors = list(response.css('a[href], link[rel="next"], link[rel="alternate"], [data-next-url], [data-load-more-url]'))
        from crawler.extraction.discovery_links import structured_source_links
        from html import escape
        for url,label in structured_source_links(response):
            anchors.insert(0,scrapy.Selector(text=f'<a href="{escape(url,quote=True)}">{label}</a>').css('a')[0])
        # Feeds and rel=next precede repeated navigation/category links.
        anchors.sort(key=lambda a: (a.attrib.get('rel') != 'next', a.attrib.get('type') not in ('application/rss+xml','application/atom+xml','text/calendar')))
        for anchor in anchors:
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
            structured_feed = anchor.attrib.get('type') in ('application/rss+xml', 'application/atom+xml', 'text/calendar') or any(x in hint for x in ('.ics', '/rss', '/feed', '/ical'))
            if structured_feed and any(word in (anchor.attrib.get('title','')+' '+label).lower() for word in ('news','aktuality')):
                continue
            role = (label + ' ' + anchor.attrib.get('rel','')).lower()
            if any(word in role for word in ('advertisement','advertising','sponsored','reklama')):
                continue
            role_hint = any(x in role for x in ('organizer','venue','program','calendar','podujatia'))
            if not pagination and not structured_feed and not role_hint and not any(word in hint for word in EVENT_LINK_HINTS):
                continue
            host = urlsplit(url).hostname.lower()
            if domain_matches(host, source.domain):
                from crawler.navigation import navigation_url, is_detail
                try:
                    url = navigation_url(url, source.domain)
                except ValueError:
                    continue
                if not url or (source.domain in ('visitbratislava.com','novacvernovka.eu','sng.sk','staratrznica.sk') and is_detail(response.url, source.domain) and not structured_feed):
                    continue
                if depth >= self.max_crawl_depth and not pagination:
                    continue
            if not domain_matches(host, source.domain):
                if self.discovered >= min(20,max(0,int(os.getenv('CRAWLER_MAX_NEW_SOURCES', '20')))):
                    continue
                # Registry -> productive candidate -> one further evidenced host.
                # Graph depth is independent of within-host navigation depth.
                if depth > self.max_crawl_depth:
                    continue
                from crawler.sources import ACTIVE_SOURCES
                if source.domain not in {s.domain for s in ACTIVE_SOURCES}:
                    if self.state is None:
                        self.state = State()
                    parent = self.state.db.execute('SELECT status,graph_depth FROM candidates WHERE domain=?',(source.domain,)).fetchone()
                    from crawler.qualification import POLICY
                    if not parent or parent['status'] not in ('probation','trusted') or parent['graph_depth'] >= POLICY.max_graph_depth:
                        continue
                    from crawler.extraction.jsonld_extractor import extract_jsonld_events
                    from crawler.extraction.source_html import extract_source_html
                    detail_evidence = bool(any(event.title and event.start_raw for event in extract_jsonld_events(response.text,response.url)) or extract_source_html(response.text,response.url) or response.css('[itemtype*="schema.org/Event"] [itemprop="startDate"]'))
                    from crawler.discovery import endpoint_rank
                    if not structured_feed and not (detail_evidence and (endpoint_rank(url)>=80 or any(x in role for x in ('organizer','venue','program','calendar','podujatia')))):
                        continue
                if self.state is None:
                    self.state = State()
                if self.state.db.execute('SELECT count(*) FROM sources').fetchone()[0] >= int(os.getenv('CRAWLER_MAX_SOURCES', '250')):
                    continue
                try:
                    if not self.state.discover(url, response.url):
                        continue
                except ValueError:
                    continue
                self.discovered += 1
                self.crawler.stats.inc_value('discovery/sources')
                continue
            yield scrapy.Request(url, priority=20 if is_detail(url,source.domain) else 15 if structured_feed else 10 if pagination else 0, callback=self.parse, errback=self.errback_source,
                                 meta={'source': source, 'crawl_depth': depth if pagination else depth + 1, 'optional_feed': structured_feed})
            followed += 1
            if followed >= self.max_links_per_page:
                break

    def _observe_instagram_profiles(self, response, source):
        # No extra requests or scheduler: inspect responses already fetched.
        if os.getenv('L4_INSTAGRAM_DISCOVERY_ENABLED', '0') != '1':
            return
        try:
            from crawler.instagram_discovery import discover_profiles, record_profiles
            if self.state is None:
                self.state = State()
            leads = discover_profiles(response, source, self.state.db)
            added = record_profiles(self.state.db, leads)
            self.crawler.stats.inc_value('instagram/accounts_discovered', added)
            self.crawler.stats.inc_value('instagram/profile_links_observed', len(leads))
        except Exception as exc:
            # Optional discovery must never break L1-L3. Do not log page data.
            self.logger.warning('Instagram account discovery unavailable (%s)', type(exc).__name__)
            self.crawler.stats.inc_value('instagram/discovery_errors')

    def closed(self, reason):
        self.logger.info('SOURCE_COUNTS=%s', self.source_counts)
        if self.state:
            self.state.close()
