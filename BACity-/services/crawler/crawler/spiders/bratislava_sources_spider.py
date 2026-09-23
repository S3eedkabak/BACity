"""Single registry-driven spider for the prototype's verified sources.

One spider is intentional: source configuration lives in sources.py, while
the extraction ladder stays shared. This is the same shape we can extend
later to a larger source registry or broad web discovery.
"""
from urllib.parse import urlparse

import scrapy

from crawler.extraction.generic_extractor import extract_best_effort
from crawler.extraction.jsonld_extractor import extract_jsonld_events
from crawler.extraction.snd_extractor import extract_snd_events
from crawler.sources import ACTIVE_SOURCES, EVENT_LINK_HINTS, SourceSeed


class BratislavaSourcesSpider(scrapy.Spider):
    name = "bratislava_sources"
    allowed_domains = sorted({source.domain for source in ACTIVE_SOURCES})

    custom_settings = {
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

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

        if depth >= 2:
            return

        links = []
        for href, text in response.css("a::attr(href), a::text").getall():
            # CSS returns attributes and text in one stream. Link extraction
            # below uses a direct node loop to keep href/text paired.
            _ = href, text

        for anchor in response.css("a[href]"):
            href = anchor.attrib.get("href", "")
            label = anchor.xpath("string(.)").get("").strip()
            absolute = response.urljoin(href).split("#", 1)[0]
            if self._is_candidate_link(absolute, label, source):
                links.append(absolute)

        seen = set()
        for url in links:
            if url in seen:
                continue
            seen.add(url)
            yield response.follow(
                url,
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

    @staticmethod
    def errback_source(failure):
        response = getattr(failure.value, "response", None)
        url = response.url if response is not None else failure.request.url
        # Keep a failed source from killing the multi-source crawl.
        spider = failure.request.callback.__self__ if failure.request.callback else None
        if spider:
            spider.logger.warning("Source request failed: %s", url)
