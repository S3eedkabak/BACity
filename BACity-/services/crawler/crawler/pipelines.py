import logging
import time
import os
import re
from datetime import datetime, timezone

import requests

from crawler.items import RawEvent
from crawler.processing.normalize import normalize_event
from crawler.processing.validate import validate_event

logger = logging.getLogger(__name__)

_KNOWN_VENUES = {
    "stará tržnica": ("Námestie SNP 25, 811 01 Bratislava", 48.1445782, 17.1112316),
    "stará trznica": ("Námestie SNP 25, 811 01 Bratislava", 48.1445782, 17.1112316),
    "slovak national theatre": ("Pribinova 17, 811 09 Bratislava", 48.1412844, 17.1235008),
    "slovenské národné divadlo": ("Pribinova 17, 811 09 Bratislava", 48.1412844, 17.1235008),
    "slovak national gallery": ("Rázusovo nábrežie 2, 811 02 Bratislava", 48.1403302, 17.1086376),
    "slovenská národná galéria": ("Rázusovo nábrežie 2, 811 02 Bratislava", 48.1403302, 17.1086376),
}


_KNOWN_ADDRESSES = {
    "námestie snp 25, 811 01 bratislava": (48.1445782, 17.1112316),
    "pribinova 17, 811 09 bratislava": (48.1412844, 17.1235008),
    "rázusovo nábrežie 2, 811 02 bratislava": (48.1403302, 17.1086376),
}


class NormalizePipeline:
    def process_item(self, item: RawEvent, spider):
        normalized = normalize_event(item)
        if normalized is None:
            logger.info("Dropped unparseable event: %r", item.title)
            spider.crawler.stats.inc_value("validation/rejected")
            spider.crawler.stats.inc_value("validation/rejected/normalization")
            raise DropItem(f"Could not normalize: {item.title}")
        return normalized


class GeocodePipeline:
    """Resolve event addresses to coordinates before validation/submission.

    A small known-venue cache covers the prototype's fixed institutions.
    Everything else uses Nominatim and is cached for the duration of the crawl.
    """

    def open_spider(self, spider):
        self.cache = {}
        from crawler.state import State
        self.state = State()
        self.last_request = 0
        self.url = spider.settings.get("GEOCODER_URL")
        self.user_agent = spider.settings.get("GEOCODER_USER_AGENT")

    def process_item(self, item, spider):
        if item.venue_name:
            known = _KNOWN_VENUES.get(item.venue_name.strip().lower())
            if known:
                address, latitude, longitude = known
                item.address = item.address or address
                item.latitude = item.latitude or latitude
                item.longitude = item.longitude or longitude

        if item.address:
            known_coords = _KNOWN_ADDRESSES.get(item.address.strip().lower())
            if known_coords:
                item.latitude, item.longitude = known_coords

        if item.latitude is not None and item.longitude is not None:
            return item

        query = item.address or item.venue_name
        if not query:
            return item

        cache_key = query.strip().lower()
        cached = self.state.db.execute("SELECT latitude,longitude FROM geocache WHERE query=? AND (expires IS NULL OR expires>?)", (cache_key, time.time())).fetchone()
        if cached:
            item.latitude, item.longitude = cached
            return item
        if cache_key in self.cache:
            item.latitude, item.longitude = self.cache[cache_key]
            return item

        if not self.url:
            return item

        try:
            time.sleep(max(0, 1.1 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            response = requests.get(
                self.url,
                params={
                    "q": f"{query}, Bratislava",
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "sk",
                    "viewbox": "16.9,48.35,17.35,48.0",
                    "bounded": 1,
                },
                headers={"User-Agent": self.user_agent},
                timeout=8,
                allow_redirects=False,
            )
            response.raise_for_status()
            if 300 <= response.status_code < 400:
                raise requests.HTTPError('Geocoder redirects are not permitted')
            results = response.json()
            if results:
                coords = (float(results[0]["lat"]), float(results[0]["lon"]))
                if 48.0 <= coords[0] <= 48.35 and 16.9 <= coords[1] <= 17.35:
                    self.cache[cache_key] = coords
                    item.latitude, item.longitude = coords
                    with self.state.db:
                        self.state.db.execute("INSERT OR REPLACE INTO geocache VALUES(?,?,?,NULL)", (cache_key, *coords))
            else:
                with self.state.db:
                    self.state.db.execute("INSERT OR REPLACE INTO geocache VALUES(?,NULL,NULL,?)", (cache_key, time.time() + 86400))
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.debug("Geocoding failed for %r: %s", query, exc)

        return item

    def close_spider(self, spider):
        self.state.close()


class PreValidatePipeline:
    def process_item(self, item, spider):
        result = validate_event(item)
        if not result.accepted or result.needs_advanced_extraction:
            spider.crawler.stats.inc_value('validation/rejected')
            reason = result.reason if not result.accepted else 'low confidence'
            reason_key = re.sub(r'[^a-z0-9]+', '_', reason.lower()).strip('_')[:60] or 'unknown'
            spider.crawler.stats.inc_value(f'validation/rejected/{reason_key}')
            raise DropItem(result.reason if not result.accepted else 'low confidence')
        return item


class ValidatePipeline:
    def process_item(self, item, spider):
        result = validate_event(item)
        if not result.accepted:
            logger.info("Rejected event %r: %s", item.title, result.reason)
            spider.crawler.stats.inc_value('validation/rejected')
            spider.crawler.stats.inc_value('validation/rejected/' + re.sub(r'[^a-z0-9]+','_',result.reason.lower()).strip('_')[:60])
            raise DropItem(f"Rejected: {result.reason}")
        if result.needs_advanced_extraction:
            logger.info(
                "Low-confidence event flagged for advanced extraction: %r",
                item.title,
            )
            spider.crawler.stats.inc_value("validation/low_confidence")
            spider.crawler.stats.inc_value('validation/rejected')
            spider.crawler.stats.inc_value('validation/rejected/low_confidence')
            raise DropItem("Insufficient confidence for publication")
        candidate_source = any(s.parser == 'structured' for s in getattr(spider,'sources',[]))
        if (item.source_reliability <= 0.6 or candidate_source) and not (
            item.latitude is not None or 'bratislava' in (item.address or '').lower()
        ):
            spider.crawler.stats.inc_value('validation/rejected')
            spider.crawler.stats.inc_value('validation/rejected/no_local_evidence')
            raise DropItem("Discovered source lacks Bratislava location evidence")
        return item


class ApiSubmitPipeline:
    def open_spider(self, spider):
        self.api_base_url = spider.settings.get("API_BASE_URL")
        self.submitted = 0
        self.failed = 0

    def process_item(self, item, spider):
        try:
            response = requests.post(
                f"{self.api_base_url}/events",
                json=_to_event_create_payload(item),
                timeout=10,
            )
            if response.status_code >= 400:
                self.failed += 1
                logger.warning(
                    "API rejected event %r: %s", item.title, response.text
                )
            else:
                self.submitted += 1
        except requests.RequestException as exc:
            self.failed += 1
            logger.warning("Failed to submit event %r: %s", item.title, exc)
        return item

    def close_spider(self, spider):
        logger.info("Submitted %d events, %d failed", self.submitted, self.failed)


class QualityAuditPipeline:
    """Non-writing live audit: same validation/completeness, no API or geocoder."""
    def process_item(self, item, spider):
        from crawler.quality import quality
        limit = 100 if any(s.parser == 'structured' for s in getattr(spider, 'sources', [])) else 1000
        if spider.crawler.stats.get_value('ingestion/queued', 0) >= limit:
            spider.crawler.stats.inc_value('resource/item_limit')
            raise DropItem('run_item_limit')
        spider.crawler.stats.inc_value('quality/events')
        spider.crawler.stats.inc_value('quality/score_total', quality(item)['score'])
        if item.end_time:
            spider.crawler.stats.inc_value('quality/with_end')
        if item.latitude is not None and item.longitude is not None:
            spider.crawler.stats.inc_value('quality/with_coordinates')
        for key,present in {'with_venue':bool(item.venue_name),'with_category':item.category not in ('','Other'),
                            'with_organizer':bool(item.organizer_name),
                            'future_events':datetime.fromisoformat(item.start_time)>datetime.now(timezone.utc)}.items():
            if present:
                spider.crawler.stats.inc_value('quality/'+key)
        spider.crawler.stats.inc_value("ingestion/queued")
        return item


class DurableSubmitPipeline(QualityAuditPipeline):
    def open_spider(self, spider):
        from crawler.state import State
        self.state = State()

    def process_item(self, item, spider):
        super().process_item(item, spider)
        self.state.enqueue(_to_event_create_payload(item))
        return item

    def close_spider(self, spider):
        from crawler.worker import deliver
        count = deliver(self.state, spider.settings.get("API_BASE_URL"), os.getenv("INGESTION_API_KEY", ""))
        spider.crawler.stats.set_value("ingestion/delivered", count)
        spider.crawler.stats.set_value("ingestion/pending", self.state.db.execute("SELECT count(*) FROM outbox").fetchone()[0])
        self.state.close()


def _to_event_create_payload(item) -> dict:
    return {
        "title": item.title,
        "description": item.description,
        "start_time": item.start_time,
        "end_time": item.end_time,
        "timezone": item.timezone,
        "venue_name": item.venue_name,
        "address": item.address,
        "latitude": item.latitude,
        "longitude": item.longitude,
        "category": item.category,
        "tags": item.tags,
        "price": item.price,
        "currency": item.currency,
        "image_url": item.image_url,
        "source_url": item.source_url,
        "source_name": item.source_name,
        "language": item.language,
        "extraction_confidence": item.extraction_confidence,
        "source_reliability": item.source_reliability,
        "status": item.event_status,
        "original_source_url": item.original_source_url,
        "temporal_evidence": item.temporal_evidence,
        "extraction_method": item.extraction_method,
        "organizer_name": item.organizer_name,
        "previous_start_time": item.previous_start_time,
    }


try:
    from scrapy.exceptions import DropItem
except ImportError:
    class DropItem(Exception):
        pass
