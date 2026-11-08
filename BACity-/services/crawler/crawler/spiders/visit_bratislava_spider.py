"""Live Phase 1 spider for Visit Bratislava.

Run from services/crawler:
    python -m scrapy crawl visit_bratislava

The spider prefers JSON-LD extraction and follows event detail pages from the
official Visit Bratislava events index. It is intentionally narrow for the
first real-data milestone before adding more sources.
"""
import scrapy

from crawler.extraction.jsonld_extractor import extract_jsonld_events
from crawler.extraction.generic_extractor import extract_best_effort


class VisitBratislavaSpider(scrapy.Spider):
    name = "visit_bratislava"
    allowed_domains = ["visitbratislava.com", "www.visitbratislava.com"]
    start_urls = ["https://www.visitbratislava.com/events/"]

    def parse(self, response):
        yield from self._extract(response)

        links = response.css(
            'a[href*="/events/"]::attr(href), '
            'a[href*="/sk/podujatia/"]::attr(href)'
        ).getall()

        seen = set()
        for href in links:
            url = response.urljoin(href).split("#", 1)[0]
            if url == response.url or url in seen:
                continue
            seen.add(url)
            yield response.follow(url, callback=self.parse_detail)

    def parse_detail(self, response):
        yield from self._extract(response)

    def _extract(self, response):
        events = extract_jsonld_events(response.text, response.url)
        if not events:
            from crawler.extraction.visit_extractor import extract_visit_events
            events = extract_visit_events(response.text, response.url)
        if not events:
            events = extract_best_effort(response.text, response.url)

        for event in events:
            yield event
