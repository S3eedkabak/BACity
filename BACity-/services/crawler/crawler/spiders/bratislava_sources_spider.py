"""Single registry-driven spider for the prototype's verified sources."""
from datetime import datetime
from urllib.parse import urlparse

import scrapy

from crawler.extraction.generic_extractor import extract_best_effort, extract_event_cards
from crawler.extraction.goout_extractor import extract_goout_events
from crawler.extraction.jsonld_extractor import extract_jsonld_events
from crawler.extraction.snd_extractor import extract_snd_events
from crawler.sources import ACTIVE_SOURCES, EVENT_LINK_HINTS, SourceSeed
from crawler.extraction.community_extractors import extract_cvernovka_events, extract_karlova_ves_events


class BratislavaSourcesSpider(scrapy.Spider):
    name = "bratislava_sources"
    allowed_domains = sorted({source.domain for source in ACTIVE_SOURCES})

    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2}
    min_sources_with_events = 5
    max_crawl_depth = 1
    max_links_per_page = 20

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sources = ACTIVE_SOURCES
        self.source_counts = {source.name: 0 for source in ACTIVE_SOURCES}

    def _source_requests(self):
        now = datetime.now()
        next_month = 1 if now.month == 12 else now.month + 1
        next_year = now.year + 1 if now.month == 12 else now.year
        for source in self.sources:
            if source.domain == "goout.net":
                yield scrapy.Request(
                    "https://goout.net/services/feeder/v1/events.json"
                    "?source=goout&locality=30&language=en"
                    "&unapproved=false&clearDomain=true",
                    callback=self.parse_goout,
                    errback=self.errback_source,
                    meta={"source": source, "crawl_depth": 0},
                )
                continue
            seed_urls = list(dict.fromkeys([source.event_url, *source.entry_urls]))[:4]
            if source.domain == "snd.sk":
                seed_urls = [
                    source.base_url,
                    f"https://snd.sk/program/{now.year}/{now.month:02d}",
                    f"https://snd.sk/program/{next_year}/{next_month:02d}",
                ]
            for seed_url in dict.fromkeys(seed_urls):
                request_meta = {"source": source, "crawl_depth": 0}
                if source.requires_js or source.domain == "snd.sk":
                    request_meta["playwright"] = True
                    if source.domain in {"snd.sk", "goout.net"}:
                        request_meta["playwright_context_kwargs"] = {
                            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0.0.0 Safari/537.36"
                        }
                yield scrapy.Request(
                    seed_url,
                    callback=self.parse,
                    errback=self.errback_source,
                    meta=request_meta,
                )
            if source.base_url != source.event_url and source.domain != "snd.sk":
                yield scrapy.Request(
                    source.base_url,
                    callback=self.parse,
                    errback=self.errback_source,
                    meta={"source": source, "crawl_depth": 0},
                )

    async def start(self):
        for request in self._source_requests():
            yield request

    def start_requests(self):
        # Compatibility for existing integrations; Scrapy uses async start().
        yield from self._source_requests()

    def parse(self, response):
        source: SourceSeed = response.meta["source"]
        depth = response.meta.get("crawl_depth", 0)

        events = list(self._extract(response, source))
        for event in events:
            yield event

        if source.domain == "snd.sk" and not events:
            self.logger.info("SND_TEXT=%s", response.xpath("string(.)").get("")[:6000])
            for iframe in response.css("iframe::attr(src)").getall():
                frame_url = response.urljoin(iframe)
                yield scrapy.Request(
                    frame_url,
                    callback=self.parse,
                    errback=self.errback_source,
                    meta={"source": source, "crawl_depth": depth, "snd_frame": True},
                )

        if depth >= self.max_crawl_depth or response.meta.get("snd_frame"):
            return

        # Stable JSON endpoints are complete and must not be treated as HTML link pages.
        if source.parser == "karlova_ves_api":
            return

        seen = set()
        for anchor in response.css("a[href]"):
            href = anchor.attrib.get("href", "")
            label = anchor.xpath("string(.)").get("").strip()
            absolute = response.urljoin(href).split("#", 1)[0]
            if absolute in seen or not self._is_candidate_link(absolute, label, source):
                continue
            seen.add(absolute)
            yield response.follow(
                absolute,
                callback=self.parse,
                errback=self.errback_source,
                meta={"source": source, "crawl_depth": depth + 1},
            )
            if len(seen) >= self.max_links_per_page:
                break

    def _extract(self, response, source: SourceSeed):
        content_type = response.headers.get('Content-Type',b'').decode('ascii','ignore').lower()
        if any(t in content_type for t in ('rss+xml','atom+xml','text/calendar')):
            from crawler.extraction.feeds import extract_feed
            events = extract_feed(response.text,response.url)
        elif source.parser == 'structured':
            from crawler.extraction.feeds import extract_feed
            events = extract_feed(response.text, response.url)
            if not events:
                from crawler.extraction.source_html import extract_source_html
                from crawler.extraction.microdata_extractor import extract_microdata_events
                events = extract_source_html(response.text, response.url) or extract_microdata_events(response.text, response.url)
            if not events:
                self.crawler.stats.inc_value('extraction/unsupported_pages')
        elif source.parser == "karlova_ves_api":
            try:
                events = extract_karlova_ves_events(response.json(), response.url)
            except ValueError:
                self.crawler.stats.inc_value("extraction/errors")
                self.logger.warning("Karlova Ves endpoint returned invalid JSON")
                events = []
        elif source.parser == "cvernovka":
            events = extract_cvernovka_events(response.text, response.url)
        elif source.domain == "snd.sk":
            events = extract_snd_events(response.text, response.url, datetime.now().year)
        else:
            from crawler.extraction.source_html import extract_source_html
            events = extract_jsonld_events(response.text, response.url) or extract_source_html(response.text, response.url)
            if not events and source.domain == 'visitbratislava.com':
                from crawler.extraction.visit_extractor import extract_visit_events
                events = extract_visit_events(response.text, response.url)
            if not events:
                from crawler.extraction.microdata_extractor import extract_microdata_events
                events = extract_microdata_events(response.text, response.url)
            if not events and source.domain in ('visitbratislava.com', 'sng.sk', 'bratislava.sk','staratrznica.sk'):
                # Listing cards are discovery evidence; incomplete cards must not
                # compete with authoritative detail dates and locations.
                return
            if not events:
                events = extract_event_cards(response.text, response.url)
            if not events:
                events = extract_best_effort(response.text, response.url)

        if getattr(self, 'crawler', None):
            self.crawler.stats.inc_value('extraction/raw', len(events))
        self.source_counts[source.name] += len(events)
        for event in events:
            event.source_name = source.name
            event.source_reliability = source.reliability_score
            event.language = source.language
            event.tags = sorted(set(event.tags or []) | set(source.tags))
            yield event

    @staticmethod
    def _is_candidate_link(url: str, label: str, source: SourceSeed) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.hostname and not (
            parsed.hostname == source.domain
            or parsed.hostname.endswith("." + source.domain)
        ):
            return False
        if source.domain == "goout.net" and not parsed.path.startswith("/en/bratislava/"):
            return False
        haystack = f"{url} {label}".lower()
        return any(hint in haystack for hint in EVENT_LINK_HINTS)

    def closed(self, reason):
        active = {name: count for name, count in self.source_counts.items() if count}
        self.logger.info("SOURCE_COUNTS=%s", active)
        if len(active) < self.min_sources_with_events:
            self.logger.error(
                "Only %d/%d configured sources produced events",
                len(active),
                len(ACTIVE_SOURCES),
            )

    def errback_source(self, failure):
        response = getattr(failure.value, "response", None)
        url = response.url if response is not None else failure.request.url
        self.logger.warning("Source request failed: %s", url)
        optional = failure.request.meta.get('optional_feed') and response is not None and response.status in (404,410)
        self.crawler.stats.inc_value('source/optional_feed_errors' if optional else 'source/request_errors')
        if not optional:
            self.crawler.stats.set_value('source/last_error',type(failure.value).__name__+': '+url.split('?',1)[0][:1000])

    def parse_goout(self, response):
        source: SourceSeed = response.meta["source"]
        try:
            data = response.json()
        except ValueError:
            self.logger.warning("GoOut feeder returned non-JSON response")
            self.crawler.stats.inc_value("extraction/errors")
            return

        events = extract_goout_events(data, response.url)
        if getattr(self, 'crawler', None):
            self.crawler.stats.inc_value('extraction/raw', len(events))
        self.source_counts[source.name] += len(events)
        for event in events:
            event.source_name = source.name
            event.source_reliability = source.reliability_score
            event.language = source.language
            yield event
        # Fixed host, fixed endpoint, monotonic page; never follow arbitrary
        # feeder-provided next URLs. Five pages cap this source at 500 shows.
        page = response.meta.get('feeder_page', 1)
        if data.get('hasNext') and page < 5:
            from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
            p = urlsplit(response.url)
            query = dict(parse_qsl(p.query)); query['page'] = str(page + 1)
            yield scrapy.Request(urlunsplit((p.scheme,p.netloc,p.path,urlencode(query),'')),
                callback=self.parse_goout,errback=self.errback_source,
                meta={'source':source,'feeder_page':page+1})
        elif data.get('hasNext'):
            self.crawler.stats.inc_value('resource/page_limit')
