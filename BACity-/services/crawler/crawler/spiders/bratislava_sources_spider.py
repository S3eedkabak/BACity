"""Single registry-driven spider for the prototype's verified sources."""
from datetime import datetime
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
        now = datetime.now()
        next_month = 1 if now.month == 12 else now.month + 1
        next_year = now.year + 1 if now.month == 12 else now.year
        for source in ACTIVE_SOURCES:
            seed_urls = [source.event_url]
            if source.domain == "snd.sk":
                seed_urls = [
                    f"https://snd.sk/program/{now.year}/{now.month:02d}",
                    f"https://snd.sk/program/{next_year}/{next_month:02d}",
                ]
            for seed_url in dict.fromkeys(seed_urls):
                request_meta = {"source": source, "crawl_depth": 0}
                if source.requires_js or source.domain == "snd.sk":
                    request_meta["playwright"] = True
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
            events = extract_snd_events(response.text, response.url, datetime.now().year)
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
