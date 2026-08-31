"""
Plain-dataclass item shape produced by extraction, before it becomes an
API `EventCreate` payload. Deliberately not a Scrapy Item subclass so the
extraction/processing modules stay importable and unit-testable without
a Scrapy runtime (relevant in this sandboxed environment where live
crawling isn't possible, and useful in general for fast unit tests).
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawEvent:
    """What extraction produces straight from a page, pre-normalization."""
    title: str
    start_raw: str                     # unparsed date/time string
    end_raw: Optional[str] = None
    description: Optional[str] = None
    venue_name: Optional[str] = None
    address: Optional[str] = None
    price_raw: Optional[str] = None
    image_url: Optional[str] = None
    category_hint: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    language: str = "sk"
    source_url: str = ""
    extraction_method: str = "unknown"   # jsonld | schema_org | generic_html | manual
    extraction_confidence: float = 0.5


@dataclass
class NormalizedEvent:
    """Output of the normalization stage — matches app.schemas.event.EventCreate shape."""
    title: str
    start_time: str                    # ISO 8601, timezone-aware
    end_time: Optional[str]
    timezone: str
    description: Optional[str]
    venue_name: Optional[str]
    address: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    image_url: Optional[str]
    category: str
    tags: list[str]
    language: str
    source_url: str
    extraction_confidence: float
