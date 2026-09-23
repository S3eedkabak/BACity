"""
Example source-specific spider, structured against Stará Tržnica's real
event listing (spec section 3: source-specific parsers are the fallback
when generic JSON-LD extraction doesn't cover a site's markup). This
illustrates the pattern Phase 3/5 spiders should follow: try JSON-LD
first, fall back to the generic HTML heuristics for anything it misses.

NOTE: live network access to this domain isn't available in every
environment this code runs in (see README "Running the crawler for real").
`run_proof.py` demonstrates the same extraction/processing pipeline this
spider feeds into, against saved fixture HTML, so the pipeline's
correctness doesn't depend on live network access to verify.
"""
import scrapy

from crawler.extraction.jsonld_extractor import extract_jsonld_events
from crawler.extraction.generic_extractor import extract_best_effort


class StaraTrznicaSpider(scrapy.Spider):
    name = "stara_trznica"
    allowed_domains = ["staratrznica.sk"]
    start_urls = ["https://staratrznica.sk/sk/program"]

    def parse(self, response):
        events = extract_jsonld_events(response.text, response.url)
        if not events:
            events = extract_best_effort(response.text, response.url)

        for event in events:
            yield event

        for link in response.css("a.event-card::attr(href), a[href*='/program/']::attr(href)").getall():
            yield response.follow(link, callback=self.parse_detail)

    def parse_detail(self, response):
        events = extract_jsonld_events(response.text, response.url)
        if not events:
            events = extract_best_effort(response.text, response.url)
        for event in events:
            yield event
