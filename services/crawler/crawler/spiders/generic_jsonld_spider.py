"""
Generic spider usable against ANY seeded source that emits JSON-LD Event
data (spec's "generic extraction" path, section 18 level 1-2) — no
source-specific parser needed. Point it at a Source's event_url and it
walks pagination/detail links looking for Event JSON-LD blocks.

This is the spider most of the 20 seed sources in crawler/sources.py
should be tried against first, before writing a source-specific spider
for the ones that don't emit structured data.
"""
import scrapy

from crawler.extraction.jsonld_extractor import extract_jsonld_events


class GenericJsonLdSpider(scrapy.Spider):
    name = "generic_jsonld"

    def __init__(self, start_url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not start_url:
            raise ValueError("generic_jsonld_spider requires -a start_url=<event listing URL>")
        self.start_urls = [start_url]

    def parse(self, response):
        events = extract_jsonld_events(response.text, response.url)
        for event in events:
            yield event

        if not events:
            self.logger.info(
                "No JSON-LD events found at %s — this source likely needs "
                "the generic HTML fallback or a source-specific spider.",
                response.url,
            )

        # Follow likely "next page" / detail links conservatively.
        for link in response.css("a::attr(href)").getall():
            if any(kw in link.lower() for kw in ("/event", "/akcia", "/podujatie", "page=")):
                yield response.follow(link, callback=self.parse)
