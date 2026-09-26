from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CrawlRunReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=255)
    base_url: str = Field(max_length=2048)
    event_url: str = Field(max_length=2048)
    source_type: str = Field(max_length=40)
    language: str = Field(default="sk", max_length=10)
    parser: str | None = Field(default=None, max_length=100)
    reliability_score: float = Field(ge=0, le=1)
    requires_js: bool = False
    crawl_frequency_minutes: int = Field(ge=15, le=10080)
    started_at: datetime
    finished_at: datetime
    success: bool
    status: Literal["healthy", "empty", "failed", "timed_out", "blocked"]
    pages_processed: int = Field(ge=0)
    items_processed: int = Field(ge=0)
    accepted_events: int = Field(ge=0)
    rejected_events: int = Field(ge=0)
    extraction_errors: int = Field(ge=0)
    skip_reasons: dict[str, int] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=2000)


class SourceAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    crawl_frequency_minutes: int | None = Field(default=None, ge=15, le=10080)
