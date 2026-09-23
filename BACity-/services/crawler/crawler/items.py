from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawEvent:
    title: str
    start_raw: str
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
    source_name: Optional[str] = None
    source_reliability: float = 0.7
    extraction_method: str = "unknown"
    extraction_confidence: float = 0.5


@dataclass
class NormalizedEvent:
    title: str
    start_time: str
    end_time: Optional[str]
    timezone: str
    description: Optional[str]
    venue_name: Optional[str]
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    price: Optional[float]
    currency: Optional[str]
    image_url: Optional[str]
    category: str
    tags: list[str]
    language: str
    source_url: str
    source_name: Optional[str]
    source_reliability: float
    extraction_confidence: float
