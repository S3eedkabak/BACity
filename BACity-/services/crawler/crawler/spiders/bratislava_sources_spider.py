"""Single registry-driven spider for the prototype's verified sources."""
from urllib.parse import urlparse

import scrapy

from crawler.extraction.generic_extractor import extract_best_effort
from crawler.extraction.jsonld_extractor import extract_jsonld_events
from crawler.extraction.snd_extractor import extract_snd_events
from crawler.sources import ACTIVE_SOURCES, EVENT_LINK_HINTS, SourceSeed


class BratislavaSourcesSpider(scrapy.Spider):
    name = "bratislava_sources"
    allowed_domains = sorted({source.domain for source in ACTIVE_SOURCES})

    custom_settings = {"CONCURRENT_REQUESTS_PER_DOMAIN": 2}
    min_sources_with_events = 5
    max_crawl_depth = 1
    max_links_per_page = 20

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_counts = {source.name: 0 for source in ACTIVE_SOURCES}

    def start_requests(self):
        for source in ACTIVE_SOURCES:
            yield scrapy.Request(
                source.event_url,
                callback=self.parse,
                errback=self.errback_source,
                meta={"source": source, "crawl_depth": 0},
            )
            if source.base_url != source.event_url:
                yield scrapy.Request(
                    source.base_url,
                    callback=self.parse,
                    errback=self.errback_source,
                    meta={"source": source, "crawl_depth": 0},
                )

    def parse(self, response):
        source: SourceSeed = response.meta["source"]
        depth = response.meta.get("crawl_depth", 0)

        yield from self._extract(response, source)

        if depth >= self.max_crawl_depth:
            return

        seen = set()
        for anchor in response.css("a[href]")[: self.max_links_per_page]:
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

    def _extract(self, response, source: SourceSeed):
        if source.domain == "snd.sk":
            events = extract_snd_events(response.text, response.url)
        else:
            events = extract_jsonld_events(response.text, response.url)
            if not events:
                events = extract_best_effort(response.text, response.url)

        self.source_counts[source.name] += len(events)
        for event in events:
            event.source_name = source.name
            event.source_reliability = source.reliability_score
            event.language = source.language
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
