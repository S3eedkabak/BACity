"""
Scrapy item pipelines wiring extraction output into processing and,
finally, the API. Kept thin: the actual logic lives in
crawler/processing/*, which is unit-tested independently of Scrapy
(see tests/) since a live crawl isn't exercised in every environment
this code runs in.
"""
import logging

import requests

from crawler.items import RawEvent
from crawler.processing.normalize import normalize_event
from crawler.processing.validate import validate_event

logger = logging.getLogger(__name__)


class NormalizePipeline:
    def process_item(self, item: RawEvent, spider):
        normalized = normalize_event(item)
        if normalized is None:
            logger.info("Dropped unparseable event: %r", item.title)
            raise DropItem(f"Could not normalize: {item.title}")
        return normalized


class ValidatePipeline:
    def process_item(self, item, spider):
        result = validate_event(item)
        if not result.accepted:
            logger.info("Rejected event %r: %s", item.title, result.reason)
            raise DropItem(f"Rejected: {result.reason}")
        if result.needs_advanced_extraction:
            logger.info("Low-confidence event flagged for advanced extraction: %r", item.title)
        return item


class ApiSubmitPipeline:
    """POSTs accepted, validated events to the API. In this sandbox the
    API isn't reachable from a live crawl (network access is restricted
    to package registries — see run_proof.py for an offline demonstration
    of the same pipeline against fixture pages), but this is the real
    integration point for a deployed worker."""

    def open_spider(self, spider):
        self.api_base_url = spider.settings.get("API_BASE_URL")
        self.submitted = 0
        self.failed = 0

    def process_item(self, item, spider):
        try:
            resp = requests.post(
                f"{self.api_base_url}/events",
                json=_to_event_create_payload(item),
                timeout=10,
            )
            if resp.status_code >= 400:
                self.failed += 1
                logger.warning("API rejected event %r: %s", item.title, resp.text)
            else:
                self.submitted += 1
        except requests.RequestException as exc:
            self.failed += 1
            logger.warning("Failed to submit event %r: %s", item.title, exc)
        return item

    def close_spider(self, spider):
        logger.info("Submitted %d events, %d failed", self.submitted, self.failed)


def _to_event_create_payload(item) -> dict:
    return {
        "title": item.title,
        "description": item.description,
        "start_time": item.start_time,
        "end_time": item.end_time,
        "timezone": item.timezone,
        "address": item.address,
        "category": item.category,
        "tags": item.tags,
        "price": item.price,
        "currency": item.currency,
        "image_url": item.image_url,
        "source_url": item.source_url,
        "language": item.language,
        "extraction_confidence": item.extraction_confidence,
    }


try:
    from scrapy.exceptions import DropItem
except ImportError:  # pragma: no cover - only needed when running under Scrapy
    class DropItem(Exception):
        pass
